import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from docx import Document as DocxDocument
from docx.enum.text import WD_COLOR_INDEX

from cases.models import Case, Redaction
from cases.models import Document as CaseDocument

from ..models import (
    Model,
    TrainingControl,
    TrainingDocument,
    TrainingRun,
    TrainingRunCaseDoc,
    TrainingRunTrainingDoc,
)
from ..tasks import (
    TrainingStopped,
    _build_spancat_pipeline,
    _prepare_examples,
    _run_training_loop,
    collect_training_data_detailed,
    train_model,
)
from .base import NetworkBlockerMixin

User = get_user_model()


def create_test_docx(path, highlights, multi_paragraph=False):
    """Helper to create a docx file with highlighted text.

    Args:
        path: Path to save the docx file
        highlights: List of (text, color) tuples or list of lists for multi-paragraph
        multi_paragraph: If True, highlights is a list of paragraphs, each containing
                        a list of (text, color) tuples
    """
    doc = DocxDocument()
    if multi_paragraph:
        for para_highlights in highlights:
            p = doc.add_paragraph()
            for text, color in para_highlights:
                run = p.add_run(text)
                if color:
                    run.font.highlight_color = color
    else:
        p = doc.add_paragraph()
        for text, color in highlights:
            run = p.add_run(text)
            if color:
                run.font.highlight_color = color
    doc.save(path)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_media_collect"))
class CollectTrainingDataDetailedTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="password")
        self.case = Case.objects.create(case_reference="C1")

        # Create a test .docx file for TrainingDocument
        self.docx_path = Path(tempfile.mkdtemp()) / "test.docx"
        create_test_docx(
            self.docx_path,
            [
                ("This is ", None),
                ("Third Party", WD_COLOR_INDEX.BRIGHT_GREEN),
                (" info. And this is ", None),
                ("Operational", WD_COLOR_INDEX.TURQUOISE),
                (" data.", None),
            ],
        )
        with open(self.docx_path, "rb") as f:
            self.training_doc = TrainingDocument.objects.create(
                name="Test Docx",
                original_file=SimpleUploadedFile(
                    "test.docx",
                    f.read(),
                    "application/vnd.openxmlformats-officedocument.\
                        wordprocessingml.document",
                ),
                created_by=self.user,
                processed=False,
            )

        # Create a CaseDocument with redactions
        self.case_doc = CaseDocument.objects.create(
            case=self.case,
            extracted_text="Some text with accepted redactions.",
            status=CaseDocument.Status.COMPLETED,
        )
        Redaction.objects.create(
            document=self.case_doc,
            start_char=15,
            end_char=23,
            text="accepted",
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
        )
        # This one should be ignored (not accepted)
        Redaction.objects.create(
            document=self.case_doc,
            start_char=0,
            end_char=4,
            text="Some",
            is_accepted=False,
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def test_collect_from_training_docs(self):
        """Test collecting data only from TrainingDocuments."""
        train_data, t_docs, c_docs = collect_training_data_detailed(
            source="training_docs"
        )

        self.assertEqual(len(train_data), 1)
        self.assertEqual(len(t_docs), 1)
        self.assertEqual(len(c_docs), 0)
        self.assertEqual(t_docs[0], self.training_doc)

        text, annotations = train_data[0]
        self.assertIn("Third Party", text)
        self.assertIn("Operational", text)
        self.assertEqual(len(annotations["entities"]), 2)
        self.assertEqual(annotations["entities"][0][2], "THIRD_PARTY")
        self.assertEqual(annotations["entities"][1][2], "OPERATIONAL")

    def test_collect_from_redactions(self):
        """Test collecting data only from CaseDocument redactions."""
        train_data, t_docs, c_docs = collect_training_data_detailed(
            source="redactions"
        )

        self.assertEqual(len(train_data), 1)
        self.assertEqual(len(t_docs), 0)
        self.assertEqual(len(c_docs), 1)
        self.assertEqual(c_docs[0], self.case_doc)

        text, annotations = train_data[0]
        self.assertEqual(text, self.case_doc.extracted_text)
        self.assertEqual(len(annotations["entities"]), 1)
        start, end, label = annotations["entities"][0]
        self.assertEqual(start, 15)
        self.assertEqual(end, 23)
        self.assertEqual(label, "OPERATIONAL")

    def test_machine_accepted_redactions_excluded_from_case_training(self):
        """Only human-decided accepts feed SpanCat — machine-accepted rows
        (auto-accept, case propagation) must be excluded."""
        machine_doc = CaseDocument.objects.create(
            case=self.case,
            extracted_text="Crime ref 42/12345/24 recorded at the station.",
            status=CaseDocument.Status.COMPLETED,
        )
        for start, end, text, mechanism in (
            (10, 21, "42/12345/24", Redaction.DecidedBy.AUTO_ACCEPT),
            (34, 41, "station", Redaction.DecidedBy.CASE_PROPAGATION),
        ):
            Redaction.objects.create(
                document=machine_doc,
                start_char=start,
                end_char=end,
                text=text,
                is_accepted=True,
                decided_by=mechanism,
                redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
            )
        train_data, _, c_docs = collect_training_data_detailed(
            source="redactions"
        )
        self.assertNotIn(machine_doc, c_docs)
        doc_texts = [text for text, _ in train_data]
        self.assertNotIn(machine_doc.extracted_text, doc_texts)

    def test_pii_redactions_excluded_from_case_training(self):
        """PII redactions from case documents must not feed into SpanCat training."""
        pii_doc = CaseDocument.objects.create(
            case=self.case,
            extracted_text="John Smith was seen near the scene.",
            status=CaseDocument.Status.COMPLETED,
        )
        Redaction.objects.create(
            document=pii_doc,
            start_char=0,
            end_char=10,
            text="John Smith",
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        train_data, _, c_docs = collect_training_data_detailed(
            source="redactions"
        )
        doc_texts = [text for text, _ in train_data]
        self.assertNotIn(pii_doc.extracted_text, doc_texts)

    def test_collect_from_both(self):
        """Test collecting data from both sources."""
        train_data, t_docs, c_docs = collect_training_data_detailed(
            source="both"
        )
        self.assertEqual(len(train_data), 2)
        self.assertEqual(len(t_docs), 1)
        self.assertEqual(len(c_docs), 1)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_media_merge"))
class CollectTrainingDataMergeTests(NetworkBlockerMixin, TestCase):
    """Tests for merging adjacent highlighted runs."""

    def setUp(self):
        self.user = User.objects.create_user("testuser2", password="password")
        self.tmp_dir = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def test_adjacent_runs_same_color_are_merged(self):
        """Test that adjacent runs with the same highlight color are merged into one entity."""
        docx_path = Path(self.tmp_dir) / "merge_test.docx"
        # Simulate Word splitting "Cheshire Police" into multiple runs
        create_test_docx(
            docx_path,
            [
                ("Cheshire ", WD_COLOR_INDEX.BRIGHT_GREEN),
                ("Police", WD_COLOR_INDEX.BRIGHT_GREEN),
                (" is here.", None),
            ],
        )
        with open(docx_path, "rb") as f:
            TrainingDocument.objects.create(
                name="Merge Test",
                original_file=SimpleUploadedFile("merge_test.docx", f.read()),
                created_by=self.user,
                processed=False,
            )

        train_data, t_docs, c_docs = collect_training_data_detailed(
            source="training_docs"
        )

        self.assertEqual(len(train_data), 1)
        text, annotations = train_data[0]
        # Should be ONE entity for "Cheshire Police", not two separate ones
        self.assertEqual(len(annotations["entities"]), 1)
        start, end, label = annotations["entities"][0]
        self.assertEqual(text[start:end], "Cheshire Police")
        self.assertEqual(label, "THIRD_PARTY")

    def test_entity_boundaries_trimmed_of_whitespace(self):
        """Test that entity boundaries are trimmed to exclude leading/trailing whitespace."""
        docx_path = Path(self.tmp_dir) / "trim_test.docx"
        # Simulate highlighted text with surrounding whitespace
        create_test_docx(
            docx_path,
            [
                ("Text ", None),
                # whitespace on both sides
                (" Jones ", WD_COLOR_INDEX.BRIGHT_GREEN),
                (" more.", None),
            ],
        )
        with open(docx_path, "rb") as f:
            TrainingDocument.objects.create(
                name="Trim Test",
                original_file=SimpleUploadedFile("trim_test.docx", f.read()),
                created_by=self.user,
                processed=False,
            )

        train_data, t_docs, c_docs = collect_training_data_detailed(
            source="training_docs"
        )

        self.assertEqual(len(train_data), 1)
        text, annotations = train_data[0]
        self.assertEqual(len(annotations["entities"]), 1)
        start, end, label = annotations["entities"][0]
        # Entity should be trimmed to just "Jones" without surrounding whitespace
        self.assertEqual(text[start:end], "Jones")

    def test_separate_highlights_remain_separate(self):
        """Test that highlights separated by non-highlighted text remain separate entities."""
        docx_path = Path(self.tmp_dir) / "separate_test.docx"
        create_test_docx(
            docx_path,
            [
                ("Ref: ", None),
                ("John", WD_COLOR_INDEX.BRIGHT_GREEN),
                (" and ", None),
                ("Jane", WD_COLOR_INDEX.BRIGHT_GREEN),
                (" are here.", None),
            ],
        )
        with open(docx_path, "rb") as f:
            TrainingDocument.objects.create(
                name="Separate Test",
                original_file=SimpleUploadedFile(
                    "separate_test.docx", f.read()
                ),
                created_by=self.user,
                processed=False,
            )

        train_data, t_docs, c_docs = collect_training_data_detailed(
            source="training_docs"
        )

        self.assertEqual(len(train_data), 1)
        text, annotations = train_data[0]
        # Should be TWO separate entities
        self.assertEqual(len(annotations["entities"]), 2)
        entity_texts = [
            text[start:end] for start, end, label in annotations["entities"]
        ]
        self.assertIn("John", entity_texts)
        self.assertIn("Jane", entity_texts)

    def test_whitespace_only_highlights_are_ignored(self):
        """Test that highlights containing only whitespace are not included as entities."""
        docx_path = Path(self.tmp_dir) / "whitespace_test.docx"
        create_test_docx(
            docx_path,
            [
                ("Text ", None),
                # whitespace-only highlight
                ("   ", WD_COLOR_INDEX.BRIGHT_GREEN),
                (" more text ", None),
                ("Valid", WD_COLOR_INDEX.TURQUOISE),
            ],
        )
        with open(docx_path, "rb") as f:
            TrainingDocument.objects.create(
                name="Whitespace Test",
                original_file=SimpleUploadedFile(
                    "whitespace_test.docx", f.read()
                ),
                created_by=self.user,
                processed=False,
            )

        train_data, t_docs, c_docs = collect_training_data_detailed(
            source="training_docs"
        )

        self.assertEqual(len(train_data), 1)
        text, annotations = train_data[0]
        # Should be ONE entity (the whitespace-only one should be ignored)
        self.assertEqual(len(annotations["entities"]), 1)
        start, end, label = annotations["entities"][0]
        self.assertEqual(text[start:end], "Valid")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_media_tables"))
class CollectTrainingDataTableTests(NetworkBlockerMixin, TestCase):
    """Tests for table cell highlight extraction in training documents."""

    def setUp(self):
        self.user = User.objects.create_user("testuser3", password="password")
        self.tmp_dir = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def _make_training_doc(self, docx_path, name):
        with open(docx_path, "rb") as f:
            return TrainingDocument.objects.create(
                name=name,
                original_file=SimpleUploadedFile(
                    docx_path.name,
                    f.read(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                created_by=self.user,
                processed=False,
            )

    def test_highlighted_table_cells_extracted_as_entities(self):
        """Highlighted cells in training doc tables are included as training entities."""
        docx_path = Path(self.tmp_dir) / "table_test.docx"
        doc = DocxDocument()
        tbl = doc.add_table(rows=2, cols=3)
        for i, header in enumerate(["Type", "Author", "Link"]):
            tbl.rows[0].cells[i].paragraphs[0].add_run(header)
        tbl.rows[1].cells[0].paragraphs[0].add_run("Action")
        author_run = (
            tbl.rows[1].cells[1].paragraphs[0].add_run("SMITH, J. #0712345")
        )
        author_run.font.highlight_color = WD_COLOR_INDEX.TURQUOISE
        link_run = tbl.rows[1].cells[2].paragraphs[0].add_run("No")
        link_run.font.highlight_color = WD_COLOR_INDEX.TURQUOISE
        doc.save(docx_path)
        self._make_training_doc(docx_path, "Table Test")

        train_data, _, _ = collect_training_data_detailed(
            source="training_docs"
        )

        self.assertEqual(len(train_data), 1)
        text, annotations = train_data[0]
        entities = annotations["entities"]

        self.assertIn("\t", text)
        self.assertIn("SMITH, J. #0712345", text)
        self.assertIn("No", text)

        operational = [e for e in entities if e[2] == "OPERATIONAL"]
        self.assertEqual(len(operational), 2)
        entity_texts = {text[s:e] for s, e, _ in operational}
        self.assertIn("SMITH, J. #0712345", entity_texts)
        self.assertIn("No", entity_texts)

    def test_table_text_format_matches_inference_format(self):
        """Table text in training data uses tab-separated cells and newline-separated rows."""
        docx_path = Path(self.tmp_dir) / "format_test.docx"
        doc = DocxDocument()
        tbl = doc.add_table(rows=2, cols=2)
        tbl.rows[0].cells[0].paragraphs[0].add_run("Col A")
        tbl.rows[0].cells[1].paragraphs[0].add_run("Col B")
        tbl.rows[1].cells[0].paragraphs[0].add_run("Row 1 A")
        run = tbl.rows[1].cells[1].paragraphs[0].add_run("Row 1 B")
        run.font.highlight_color = WD_COLOR_INDEX.TURQUOISE
        doc.save(docx_path)
        self._make_training_doc(docx_path, "Format Test")

        train_data, _, _ = collect_training_data_detailed(
            source="training_docs"
        )

        self.assertEqual(len(train_data), 1)
        text, annotations = train_data[0]

        self.assertIn("Col A\tCol B", text)
        self.assertIn("Row 1 A\tRow 1 B", text)

        entity_texts = [text[s:e] for s, e, _ in annotations["entities"]]
        self.assertIn("Row 1 B", entity_texts)

    def test_paragraphs_and_tables_both_extracted_in_order(self):
        """Paragraph highlights and table cell highlights are both extracted from the same doc."""
        docx_path = Path(self.tmp_dir) / "mixed_test.docx"
        doc = DocxDocument()
        p = doc.add_paragraph()
        p.add_run("Before: ")
        para_run = p.add_run("ParaEntity")
        para_run.font.highlight_color = WD_COLOR_INDEX.BRIGHT_GREEN
        tbl = doc.add_table(rows=1, cols=2)
        tbl.rows[0].cells[0].paragraphs[0].add_run("Cell A")
        cell_run = tbl.rows[0].cells[1].paragraphs[0].add_run("CellEntity")
        cell_run.font.highlight_color = WD_COLOR_INDEX.TURQUOISE
        doc.save(docx_path)
        self._make_training_doc(docx_path, "Mixed Test")

        train_data, _, _ = collect_training_data_detailed(
            source="training_docs"
        )

        self.assertEqual(len(train_data), 1)
        text, annotations = train_data[0]

        self.assertIn("ParaEntity", text)
        self.assertIn("CellEntity", text)
        self.assertEqual(len(annotations["entities"]), 2)

        third_party = [
            e for e in annotations["entities"] if e[2] == "THIRD_PARTY"
        ]
        operational = [
            e for e in annotations["entities"] if e[2] == "OPERATIONAL"
        ]
        self.assertEqual(len(third_party), 1)
        self.assertEqual(len(operational), 1)
        self.assertEqual(
            text[third_party[0][0] : third_party[0][1]], "ParaEntity"
        )
        self.assertEqual(
            text[operational[0][0] : operational[0][1]], "CellEntity"
        )

        para_pos = text.index("ParaEntity")
        cell_pos = text.index("CellEntity")
        self.assertLess(para_pos, cell_pos)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_model_train"))
class TrainModelTests(NetworkBlockerMixin, TestCase):
    """Tests for the full SpanCat training pipeline."""

    def setUp(self):
        self.user = User.objects.create_user("trainuser", password="password")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def test_train_model_aborts_if_another_running(self):
        """
        A second run would double the machine's load for no benefit. The
        guard is the live run's own heartbeat — the old one consulted
        django-q Task rows, which only exist once a task has finished, so it
        never saw a run in progress and never stopped anything.
        """
        control = TrainingControl.get()
        control.started_at = timezone.now()
        control.heartbeat_at = timezone.now()
        control.pid = 4242
        control.save()

        with patch("training.tasks.collect_training_data_detailed") as collect:
            train_model(source="both")

        collect.assert_not_called()

    def test_train_model_replaces_an_abandoned_run(self):
        """A run killed outright leaves its marker behind; a stale heartbeat
        must not block the next attempt forever."""
        control = TrainingControl.get()
        control.started_at = timezone.now() - timedelta(hours=4)
        control.heartbeat_at = timezone.now() - timedelta(hours=4)
        control.pid = 4242
        control.save()

        with patch("training.tasks.collect_training_data_detailed") as collect:
            collect.return_value = ([], [], [])
            train_model(source="both")

        collect.assert_called_once()

    def test_train_model_aborts_with_insufficient_data(self):
        """train_model() aborts if fewer than 75 training examples exist."""

        initial_model_count = Model.objects.count()
        train_model(source="both")
        self.assertEqual(Model.objects.count(), initial_model_count)

    @patch("training.tasks._run_training_loop")
    @patch("training.tasks._prepare_examples")
    @patch("training.tasks._build_spancat_pipeline")
    @patch("training.tasks.collect_training_data_detailed")
    def test_train_model_creates_spancat_model(
        self,
        mock_collect,
        mock_build_pipeline,
        mock_prepare,
        mock_run_loop,
    ):
        """train_model() creates a Model with model_type=SPANCAT and a TrainingRun."""

        # Provide enough fake training data (>=75 entries)
        fake_data = [
            (f"text {i}", {"entities": [(0, 4, "THIRD_PARTY")]})
            for i in range(75)
        ]
        mock_collect.return_value = (fake_data, [], [])

        mock_nlp = MagicMock()
        mock_nlp.pipe_names = []
        mock_build_pipeline.return_value = mock_nlp
        mock_prepare.return_value = [MagicMock()]
        mock_run_loop.return_value = {
            "spans_sc_p": 0.8,
            "spans_sc_r": 0.75,
            "spans_sc_f": 0.77,
        }

        initial_model_count = Model.objects.count()
        train_model(source="redactions")

        self.assertEqual(Model.objects.count(), initial_model_count + 1)
        new_model = Model.objects.order_by("-created_at").first()
        self.assertFalse(new_model.is_active)
        self.assertAlmostEqual(new_model.precision, 0.8)
        self.assertAlmostEqual(new_model.recall, 0.75)
        self.assertAlmostEqual(new_model.f1_score, 0.77)

        self.assertEqual(
            TrainingRun.objects.filter(model=new_model).count(), 1
        )

    @patch("training.tasks._run_training_loop")
    @patch("training.tasks._prepare_examples")
    @patch("training.tasks._build_spancat_pipeline")
    @patch("training.tasks.collect_training_data_detailed")
    def test_train_model_cleans_up_on_exception(
        self,
        mock_collect,
        mock_build_pipeline,
        mock_prepare,
        mock_run_loop,
    ):
        """train_model() removes the output directory if training raises an exception."""

        fake_data = [
            (f"text {i}", {"entities": [(0, 4, "THIRD_PARTY")]})
            for i in range(75)
        ]
        mock_collect.return_value = (fake_data, [], [])

        mock_build_pipeline.side_effect = RuntimeError("spaCy load failed")

        initial_model_count = Model.objects.count()
        with self.assertRaises(RuntimeError):
            train_model(source="redactions")

        # No model should be created
        self.assertEqual(Model.objects.count(), initial_model_count)

    @patch("training.tasks._run_training_loop")
    @patch("training.tasks._prepare_examples")
    @patch("training.tasks._build_spancat_pipeline")
    @patch("training.tasks.collect_training_data_detailed")
    def test_train_model_records_training_and_case_docs(
        self,
        mock_collect,
        mock_build_pipeline,
        mock_prepare,
        mock_run_loop,
    ):
        """train_model() creates TrainingRunTrainingDoc and TrainingRunCaseDoc for used docs."""

        case = Case.objects.create(case_reference="TRACK1")
        case_doc = CaseDocument.objects.create(
            case=case,
            extracted_text="Some case text",
            status=CaseDocument.Status.COMPLETED,
        )
        training_doc = TrainingDocument.objects.create(
            name="Track Doc",
            original_file=SimpleUploadedFile("track.docx", b"content"),
            created_by=self.user,
        )

        fake_data = [
            (f"text {i}", {"entities": [(0, 4, "THIRD_PARTY")]})
            for i in range(75)
        ]
        mock_collect.return_value = (fake_data, [training_doc], [case_doc])

        mock_nlp = MagicMock()
        mock_nlp.pipe_names = []
        mock_build_pipeline.return_value = mock_nlp
        mock_prepare.return_value = [MagicMock()]
        mock_run_loop.return_value = {
            "spans_sc_p": 0.8,
            "spans_sc_r": 0.75,
            "spans_sc_f": 0.77,
        }

        train_model(source="both")

        new_model = Model.objects.order_by("-created_at").first()
        training_run = TrainingRun.objects.get(model=new_model)

        self.assertEqual(
            TrainingRunTrainingDoc.objects.filter(
                training_run=training_run
            ).count(),
            1,
        )
        self.assertEqual(
            TrainingRunCaseDoc.objects.filter(
                training_run=training_run
            ).count(),
            1,
        )


class BuildSpancatPipelineTests(NetworkBlockerMixin, TestCase):
    @patch("spacy.load")
    def test_builds_pipeline_with_spancat(self, mock_load):
        mock_nlp = MagicMock()
        mock_nlp.pipe_names = ["tok2vec", "ner", "parser"]
        mock_nlp.get_pipe.return_value.model.get_dim.return_value = 96
        mock_spancat = MagicMock()
        mock_nlp.add_pipe.return_value = mock_spancat
        mock_load.return_value = mock_nlp

        result = _build_spancat_pipeline()

        mock_load.assert_called_once_with("en_core_web_lg")
        mock_nlp.remove_pipe.assert_any_call("ner")
        mock_nlp.remove_pipe.assert_any_call("parser")
        mock_nlp.add_pipe.assert_called_once()
        self.assertEqual(mock_nlp.add_pipe.call_args[0][0], "spancat")
        mock_spancat.add_label.assert_any_call("THIRD_PARTY")
        mock_spancat.add_label.assert_any_call("OPERATIONAL")
        self.assertEqual(result, mock_nlp)


class PrepareExamplesTests(NetworkBlockerMixin, TestCase):
    def test_valid_spans_included(self):
        mock_nlp = MagicMock()
        mock_doc = MagicMock()
        mock_ref = MagicMock()
        mock_span = MagicMock()

        mock_nlp.make_doc.return_value = mock_doc
        mock_doc.copy.return_value = mock_ref
        mock_ref.char_span.return_value = mock_span

        train_data = [("Hello world", {"entities": [(0, 5, "THIRD_PARTY")]})]

        with patch("training.tasks.Example") as mock_example:
            mock_example.return_value = MagicMock()
            examples = _prepare_examples(mock_nlp, train_data)

        self.assertEqual(len(examples), 1)
        mock_ref.char_span.assert_called_once_with(
            0, 5, label="THIRD_PARTY", alignment_mode="contract"
        )

    def test_misaligned_spans_dropped(self):
        mock_nlp = MagicMock()
        mock_doc = MagicMock()
        mock_ref = MagicMock()

        mock_nlp.make_doc.return_value = mock_doc
        mock_doc.copy.return_value = mock_ref
        mock_ref.char_span.return_value = None  # misaligned span

        train_data = [("Hello world", {"entities": [(0, 5, "THIRD_PARTY")]})]

        with patch("training.tasks.Example") as mock_example:
            mock_example.return_value = MagicMock()
            examples = _prepare_examples(mock_nlp, train_data)

        self.assertEqual(len(examples), 1)
        # The span was dropped, ref.spans["sc"] should be set to empty list
        mock_ref.spans.__setitem__.assert_called_with("sc", [])


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_media_train_loop"))
class RunTrainingLoopTests(NetworkBlockerMixin, TestCase):
    def test_early_stopping_triggered(self):
        mock_nlp = MagicMock()
        mock_nlp.resume_training.return_value = MagicMock()
        mock_nlp.evaluate.return_value = {
            "spans_sc_f": 0.0,
            "spans_sc_p": 0.0,
            "spans_sc_r": 0.0,
        }

        with tempfile.TemporaryDirectory() as output_dir:
            _run_training_loop(mock_nlp, [], [], output_dir)

        # patience=3, so loop runs exactly 3 epochs before early stopping
        self.assertEqual(mock_nlp.evaluate.call_count, 3)

    def test_saves_to_disk_when_no_improvement(self):
        mock_nlp = MagicMock()
        mock_nlp.resume_training.return_value = MagicMock()
        mock_nlp.evaluate.return_value = {
            "spans_sc_f": 0.0,
            "spans_sc_p": 0.0,
            "spans_sc_r": 0.0,
        }

        with tempfile.TemporaryDirectory() as output_dir:
            result = _run_training_loop(mock_nlp, [], [], output_dir)

        # When best_f1==0.0, nlp.to_disk is still called after the loop
        mock_nlp.to_disk.assert_called_once()
        self.assertEqual(result.get("spans_sc_f"), 0.0)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_media_edge"))
class CollectTrainingDataDetailedEdgeCasesTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user("edgeuser", password="password")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def test_ds_information_redactions_excluded(self):
        """DS_INFORMATION redactions are excluded from training data."""
        from cases.models import Case, Redaction
        from cases.models import Document as CaseDocument

        case = Case.objects.create(case_reference="EDGE1")
        case_doc = CaseDocument.objects.create(
            case=case,
            extracted_text="DS info here and other stuff.",
            status=CaseDocument.Status.COMPLETED,
        )
        Redaction.objects.create(
            document=case_doc,
            start_char=0,
            end_char=7,
            text="DS info",
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
        )

        train_data, _, _ = collect_training_data_detailed(source="redactions")
        # DS_INFORMATION excluded → entities empty → no training data for this doc
        self.assertEqual(len(train_data), 0)

    def test_completed_doc_with_no_text_skipped(self):
        """A completed document with empty extracted_text is skipped."""
        from cases.models import Case
        from cases.models import Document as CaseDocument

        case = Case.objects.create(case_reference="EDGE2")
        CaseDocument.objects.create(
            case=case,
            extracted_text="",
            status=CaseDocument.Status.COMPLETED,
        )

        train_data, _, _ = collect_training_data_detailed(source="redactions")
        self.assertEqual(len(train_data), 0)

    def test_bad_docx_logs_error_and_continues(self):
        """A corrupted training document is skipped without raising an exception."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        bad_file = SimpleUploadedFile("bad.docx", b"not a valid docx file")
        TrainingDocument.objects.create(
            name="Bad Docx",
            original_file=bad_file,
            created_by=self.user,
            processed=False,
        )

        train_data, t_docs, _ = collect_training_data_detailed(
            source="training_docs"
        )
        self.assertEqual(len(train_data), 0)
        self.assertEqual(len(t_docs), 0)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_media_stop"))
class TrainingStopTests(NetworkBlockerMixin, TestCase):
    """Stopping a run must leave nothing behind and nothing registered."""

    def _nlp(self):
        nlp = MagicMock()
        nlp.resume_training.return_value = MagicMock()
        nlp.evaluate.return_value = {
            "spans_sc_f": 0.5,
            "spans_sc_p": 0.5,
            "spans_sc_r": 0.5,
        }
        return nlp

    def _request_stop(self):
        control = TrainingControl.get()
        control.cancel_requested = True
        control.save()

    def test_loop_stops_at_the_first_epoch_check(self):
        self._request_stop()
        nlp = self._nlp()

        with tempfile.TemporaryDirectory() as output_dir:
            with self.assertRaises(TrainingStopped):
                _run_training_loop(nlp, [], [], output_dir)

        # Abandoned before any training happened at all.
        nlp.update.assert_not_called()
        nlp.evaluate.assert_not_called()

    def test_loop_runs_normally_when_no_stop_is_requested(self):
        nlp = self._nlp()

        with tempfile.TemporaryDirectory() as output_dir:
            _run_training_loop(nlp, [], [], output_dir)

        self.assertTrue(nlp.evaluate.called)

    def test_preparing_examples_is_interruptible(self):
        """
        The slowest phase of a long run, and the one that had no check: a stop
        during it used to appear to do nothing until epoch 1 began.
        """
        import spacy

        self._request_stop()
        nlp = spacy.blank("en")
        train_data = [(f"text {i}", {"entities": []}) for i in range(40)]

        with patch.object(nlp, "make_doc", wraps=nlp.make_doc) as spy:
            with self.assertRaises(TrainingStopped):
                _prepare_examples(nlp, train_data)

        # Gave up partway rather than building all forty.
        self.assertGreater(spy.call_count, 0)
        self.assertLess(spy.call_count, len(train_data))

    def test_preparing_examples_completes_when_not_stopped(self):
        import spacy

        nlp = spacy.blank("en")
        train_data = [(f"text {i}", {"entities": []}) for i in range(40)]

        examples = _prepare_examples(nlp, train_data)

        self.assertEqual(len(examples), 40)

    @patch("training.tasks._run_training_loop")
    @patch("training.tasks._prepare_examples")
    @patch("training.tasks._build_spancat_pipeline")
    @patch("training.tasks.collect_training_data_detailed")
    def test_cancelled_run_registers_no_model_and_leaves_no_directory(
        self,
        mock_collect,
        mock_build_pipeline,
        mock_prepare,
        mock_run_loop,
    ):
        mock_collect.return_value = (
            [
                (f"text {i}", {"entities": [(0, 4, "THIRD_PARTY")]})
                for i in range(75)
            ],
            [],
            [],
        )
        nlp = MagicMock()
        nlp.pipe_names = []
        mock_build_pipeline.return_value = nlp
        mock_prepare.return_value = [MagicMock()]

        created = []

        def _cancel(nlp_, train, dev, output_dir):
            # The real loop has already made the directory by this point.
            created.append(Path(output_dir))
            raise TrainingStopped("during epoch 1")

        mock_run_loop.side_effect = _cancel

        before = Model.objects.count()
        train_model(source="redactions")

        self.assertEqual(Model.objects.count(), before)
        self.assertEqual(TrainingRun.objects.count(), 0)
        self.assertFalse(
            created[0].exists(), "partial model dir was left behind"
        )
        # Flag cleared so the next run is not killed by a stale stop.
        self.assertFalse(TrainingControl.get().cancel_requested)

    @patch("training.tasks._run_training_loop")
    @patch("training.tasks._prepare_examples")
    @patch("training.tasks._build_spancat_pipeline")
    @patch("training.tasks.collect_training_data_detailed")
    def test_a_stale_stop_flag_does_not_kill_the_next_run(
        self,
        mock_collect,
        mock_build_pipeline,
        mock_prepare,
        mock_run_loop,
    ):
        control = TrainingControl.get()
        control.cancel_requested = True
        control.save()

        mock_collect.return_value = (
            [
                (f"text {i}", {"entities": [(0, 4, "THIRD_PARTY")]})
                for i in range(75)
            ],
            [],
            [],
        )
        nlp = MagicMock()
        nlp.pipe_names = []
        mock_build_pipeline.return_value = nlp
        mock_prepare.return_value = [MagicMock()]
        mock_run_loop.return_value = {
            "spans_sc_p": 0.9,
            "spans_sc_r": 0.9,
            "spans_sc_f": 0.9,
        }

        train_model(source="redactions")

        self.assertFalse(TrainingControl.get().cancel_requested)
        self.assertEqual(Model.objects.count(), 1)


class SuggesterCeilingTests(NetworkBlockerMixin, TestCase):
    """The ceiling is configurable because it has to be sized to the host."""

    def _sizes(self, nlp):
        return nlp.get_pipe("spancat").suggester.keywords["sizes"]

    def test_defaults_to_the_configured_ceiling(self):
        with override_settings(SPANCAT_MAX_SPAN_TOKENS=40):
            nlp = _build_spancat_pipeline()
        self.assertEqual(max(self._sizes(nlp)), 40)
        self.assertEqual(min(self._sizes(nlp)), 1)

    def test_honours_an_overridden_ceiling(self):
        with override_settings(SPANCAT_MAX_SPAN_TOKENS=12):
            nlp = _build_spancat_pipeline()
        self.assertEqual(max(self._sizes(nlp)), 12)


class SplitLongAnnotationTests(NetworkBlockerMixin, TestCase):
    """
    Annotations longer than the suggester ceiling are unreachable: never
    proposed, never learned, and counted against recall. Dividing them at
    clause boundaries makes the material learnable.
    """

    def setUp(self):
        import spacy

        self.nlp = spacy.blank("en")

    def _spans(self, text, entities, max_tokens):
        examples = _prepare_examples(
            self.nlp, [(text, {"entities": entities})], max_tokens
        )
        return list(examples[0].reference.spans["sc"])

    def test_a_short_annotation_is_left_alone(self):
        text = "Attended LYMM; scene secured."
        spans = self._spans(text, [(0, len(text), "OPERATIONAL")], 40)

        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].text, text)

    def test_a_long_annotation_is_divided(self):
        text = (
            "Custody interview conducted with the suspect. "
            "Suspect asked to account for movements and intent. "
            "Evidential points put: CCTV time-stamps and witness accounts. "
            "Suspect provided a prepared statement and said no comment."
        )
        spans = self._spans(text, [(0, len(text), "OPERATIONAL")], 10)

        self.assertGreater(len(spans), 1)
        self.assertTrue(
            all(len(s) <= 10 for s in spans), [len(s) for s in spans]
        )
        self.assertTrue(all(s.label_ == "OPERATIONAL" for s in spans))

    def test_the_pieces_still_cover_the_whole_annotation(self):
        """Dividing must not lose material — that would under-redact."""
        text = (
            "Circumstances recorded; description provided; CCTV logged. "
            "Further enquiries completed; statements indexed; exhibits stored."
        )
        spans = self._spans(text, [(0, len(text), "OPERATIONAL")], 8)

        self.assertEqual(spans[0].start_char, 0)
        self.assertEqual(spans[-1].end_char, len(text.rstrip()))
        # Consecutive, with no gap bigger than the separator between them.
        for earlier, later in zip(spans, spans[1:], strict=False):
            self.assertLessEqual(later.start_char - earlier.end_char, 2)

    def test_pieces_prefer_clause_boundaries(self):
        text = (
            "Attended the scene; accounts obtained; BWV bookmarked. "
            "CCTV enquiries made; continuity recorded; stills circulated."
        )
        spans = self._spans(text, [(0, len(text), "OPERATIONAL")], 12)

        # Every piece but the last should finish on a boundary character.
        for span in spans[:-1]:
            self.assertTrue(
                span.text.rstrip().endswith((".", ";", "!", "?")),
                f"piece did not end at a boundary: {span.text!r}",
            )

    def test_text_with_no_boundaries_is_still_divided(self):
        """A wall of words with no punctuation must not defeat the split."""
        text = " ".join(f"word{i}" for i in range(60))
        spans = self._spans(text, [(0, len(text), "OPERATIONAL")], 10)

        self.assertEqual(len(spans), 6)
        self.assertTrue(all(len(s) <= 10 for s in spans))

    def test_splitting_is_off_when_no_ceiling_is_given(self):
        text = " ".join(f"word{i}" for i in range(60))
        spans = self._spans(text, [(0, len(text), "OPERATIONAL")], None)

        self.assertEqual(len(spans), 1)


class TrainingHeartbeatTests(NetworkBlockerMixin, TestCase):
    """
    A run has to say it is alive. Inferring it from the task queue was wrong
    in the way that mattered: when django-q reaped a task at its timeout the
    queue entry vanished while the process kept training, so the UI showed
    nothing running and the Stop button was never offered.
    """

    def test_a_fresh_heartbeat_means_running(self):
        control = TrainingControl.get()
        control.heartbeat_at = timezone.now()
        control.save()

        self.assertTrue(TrainingControl.get().is_running)
        self.assertFalse(TrainingControl.get().is_stale)

    def test_an_old_heartbeat_means_abandoned_not_running(self):
        control = TrainingControl.get()
        control.started_at = timezone.now() - timedelta(hours=3)
        control.heartbeat_at = timezone.now() - timedelta(hours=3)
        control.pid = 999
        control.save()

        fresh = TrainingControl.get()
        self.assertFalse(fresh.is_running)
        self.assertTrue(fresh.is_stale)

    def test_no_heartbeat_at_all_means_idle(self):
        fresh = TrainingControl.get()
        self.assertFalse(fresh.is_running)
        self.assertFalse(fresh.is_stale)

    @patch("training.tasks._train_model_inner")
    def test_a_run_claims_and_releases_the_slot(self, inner):
        seen = {}

        def _record(source):
            control = TrainingControl.get()
            seen["running"] = control.is_running
            seen["pid"] = control.pid

        inner.side_effect = _record
        train_model(source="training_docs")

        self.assertTrue(seen["running"], "run was not visible while running")
        self.assertEqual(seen["pid"], os.getpid())
        # Released afterwards, so the next run is not blocked.
        self.assertFalse(TrainingControl.get().is_running)
        self.assertIsNone(TrainingControl.get().pid)

    @patch("training.tasks._train_model_inner")
    def test_the_slot_is_released_even_when_training_raises(self, inner):
        inner.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            train_model(source="training_docs")

        self.assertFalse(TrainingControl.get().is_running)
        self.assertIsNone(TrainingControl.get().started_at)

    @patch("training.tasks._train_model_inner")
    def test_claiming_clears_a_stale_stop_request(self, inner):
        control = TrainingControl.get()
        control.cancel_requested = True
        control.save()

        train_model(source="training_docs")

        self.assertFalse(TrainingControl.get().cancel_requested)
