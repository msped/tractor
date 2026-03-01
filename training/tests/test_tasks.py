import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from docx import Document as DocxDocument
from docx.enum.text import WD_COLOR_INDEX

from cases.models import Case, Redaction
from cases.models import Document as CaseDocument

from ..models import Model, TrainingDocument, TrainingRun
from ..tasks import (
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
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        # This one should be ignored
        Redaction.objects.create(
            document=self.case_doc,
            start_char=0,
            end_char=4,
            text="Some",
            is_accepted=False,
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def test_collect_from_training_docs(self):
        """Test collecting data only from TrainingDocuments."""
        train_data, t_docs, c_docs = collect_training_data_detailed(source="training_docs")

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
        train_data, t_docs, c_docs = collect_training_data_detailed(source="redactions")

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
        self.assertEqual(label, "THIRD_PARTY")

    def test_collect_from_both(self):
        """Test collecting data from both sources."""
        train_data, t_docs, c_docs = collect_training_data_detailed(source="both")
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

        train_data, t_docs, c_docs = collect_training_data_detailed(source="training_docs")

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

        train_data, t_docs, c_docs = collect_training_data_detailed(source="training_docs")

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
                ("Name: ", None),
                ("John", WD_COLOR_INDEX.BRIGHT_GREEN),
                (" and ", None),
                ("Jane", WD_COLOR_INDEX.BRIGHT_GREEN),
                (" are here.", None),
            ],
        )
        with open(docx_path, "rb") as f:
            TrainingDocument.objects.create(
                name="Separate Test",
                original_file=SimpleUploadedFile("separate_test.docx", f.read()),
                created_by=self.user,
                processed=False,
            )

        train_data, t_docs, c_docs = collect_training_data_detailed(source="training_docs")

        self.assertEqual(len(train_data), 1)
        text, annotations = train_data[0]
        # Should be TWO separate entities
        self.assertEqual(len(annotations["entities"]), 2)
        entity_texts = [text[start:end] for start, end, label in annotations["entities"]]
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
                original_file=SimpleUploadedFile("whitespace_test.docx", f.read()),
                created_by=self.user,
                processed=False,
            )

        train_data, t_docs, c_docs = collect_training_data_detailed(source="training_docs")

        self.assertEqual(len(train_data), 1)
        text, annotations = train_data[0]
        # Should be ONE entity (the whitespace-only one should be ignored)
        self.assertEqual(len(annotations["entities"]), 1)
        start, end, label = annotations["entities"][0]
        self.assertEqual(text[start:end], "Valid")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_media_train"))
class TrainModelTests(NetworkBlockerMixin, TestCase):
    """Tests for the full SpanCat training pipeline."""

    def setUp(self):
        self.user = User.objects.create_user("trainuser", password="password")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    @patch("training.tasks.Task")
    def test_train_model_aborts_if_another_running(self, mock_task):
        """train_model() aborts if another task is already in progress."""
        mock_task.objects.filter.return_value.count.return_value = 1

        result = train_model(source="both")
        self.assertIsNone(result)

    @patch("training.tasks.Task")
    def test_train_model_aborts_with_insufficient_data(self, mock_task):
        """train_model() aborts if fewer than 25 training examples exist."""
        mock_task.objects.filter.return_value.count.return_value = 0

        initial_model_count = Model.objects.count()
        train_model(source="both")
        self.assertEqual(Model.objects.count(), initial_model_count)

    @patch("training.tasks._run_training_loop")
    @patch("training.tasks._prepare_examples")
    @patch("training.tasks._build_spancat_pipeline")
    @patch("training.tasks.collect_training_data_detailed")
    @patch("training.tasks.Task")
    def test_train_model_creates_spancat_model(
        self, mock_task, mock_collect, mock_build_pipeline, mock_prepare, mock_run_loop
    ):
        """train_model() creates a Model with model_type=SPANCAT and a TrainingRun."""
        mock_task.objects.filter.return_value.count.return_value = 0

        # Provide enough fake training data (>=25 entries)
        fake_data = [(f"text {i}", {"entities": [(0, 4, "THIRD_PARTY")]}) for i in range(25)]
        mock_collect.return_value = (fake_data, [], [])

        mock_nlp = MagicMock()
        mock_nlp.pipe_names = []
        mock_build_pipeline.return_value = mock_nlp
        mock_prepare.return_value = [MagicMock()]
        mock_run_loop.return_value = {"spans_sc_p": 0.8, "spans_sc_r": 0.75, "spans_sc_f": 0.77}

        initial_model_count = Model.objects.count()
        train_model(source="redactions")

        self.assertEqual(Model.objects.count(), initial_model_count + 1)
        new_model = Model.objects.order_by("-created_at").first()
        self.assertFalse(new_model.is_active)
        self.assertAlmostEqual(new_model.precision, 0.8)
        self.assertAlmostEqual(new_model.recall, 0.75)
        self.assertAlmostEqual(new_model.f1_score, 0.77)

        self.assertEqual(TrainingRun.objects.filter(model=new_model).count(), 1)

    @patch("training.tasks._run_training_loop")
    @patch("training.tasks._prepare_examples")
    @patch("training.tasks._build_spancat_pipeline")
    @patch("training.tasks.collect_training_data_detailed")
    @patch("training.tasks.Task")
    def test_train_model_cleans_up_on_exception(
        self, mock_task, mock_collect, mock_build_pipeline, mock_prepare, mock_run_loop
    ):
        """train_model() removes the output directory if training raises an exception."""
        mock_task.objects.filter.return_value.count.return_value = 0

        fake_data = [(f"text {i}", {"entities": [(0, 4, "THIRD_PARTY")]}) for i in range(25)]
        mock_collect.return_value = (fake_data, [], [])

        mock_build_pipeline.side_effect = RuntimeError("spaCy load failed")

        initial_model_count = Model.objects.count()
        with self.assertRaises(RuntimeError):
            train_model(source="redactions")

        # No model should be created
        self.assertEqual(Model.objects.count(), initial_model_count)
