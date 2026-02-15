import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import spacy
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
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
        self.docx_path = Path(settings.MEDIA_ROOT) / "test.docx"
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
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
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

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_adjacent_runs_same_color_are_merged(self):
        """Test that adjacent runs with the same highlight color are merged into one entity."""
        docx_path = Path(settings.MEDIA_ROOT) / "merge_test.docx"
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
        docx_path = Path(settings.MEDIA_ROOT) / "trim_test.docx"
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
        docx_path = Path(settings.MEDIA_ROOT) / "separate_test.docx"
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
        docx_path = Path(settings.MEDIA_ROOT) / "whitespace_test.docx"
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


@override_settings(
    BASE_DIR=Path(tempfile.mkdtemp(prefix="test_base_train")),
    HIGHLIGHT_COLOR_TO_LABEL={
        "BRIGHT_GREEN": "THIRD_PARTY",
        "TURQUOISE": "OPERATIONAL",
    },
)
class TrainModelTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="password", first_name="Test", last_name="User")
        self.mock_train_data = [(f"text {i}", {"entities": [(0, 4, "LABEL")]}) for i in range(25)]
        # Use real TrainingDocument objects. The ORM needs them to create
        # related TrainingRunTrainingDoc objects.
        self.used_tdocs = []
        for i in range(2):
            self.used_tdocs.append(TrainingDocument.objects.create(name=f"tdoc-{i}", created_by=self.user))

        # Use real CaseDocument objects for the same reason.
        self.used_cdocs = []
        case = Case.objects.create(case_reference="C-TEST")
        for i in range(2):
            self.used_cdocs.append(
                CaseDocument.objects.create(case=case, original_file=SimpleUploadedFile(f"cdoc-{i}.txt", b"content"))
            )

        # Mock dependencies
        self.collect_patcher = patch("training.tasks.collect_training_data_detailed")
        self.mock_collect = self.collect_patcher.start()
        self.mock_collect.return_value = (
            self.mock_train_data,
            self.used_tdocs,
            self.used_cdocs,
        )

        self.build_pipeline_patcher = patch("training.tasks._build_spancat_pipeline")
        self.mock_build_pipeline = self.build_pipeline_patcher.start()

        # Create a mock NLP object that behaves like a SpanCat pipeline
        self.mock_nlp = MagicMock()
        real_nlp = spacy.blank("en")
        self.mock_nlp.make_doc.side_effect = real_nlp.make_doc
        self.mock_nlp.evaluate.return_value = {
            "spans_sc_f": 0.875,
            "spans_sc_p": 0.9,
            "spans_sc_r": 0.85,
        }
        mock_optimizer = MagicMock()
        self.mock_nlp.resume_training.return_value = mock_optimizer
        self.mock_build_pipeline.return_value = self.mock_nlp

        self.prepare_examples_patcher = patch("training.tasks._prepare_examples")
        self.mock_prepare_examples = self.prepare_examples_patcher.start()
        # Return mock Example objects (one per training data item)
        self.mock_prepare_examples.return_value = [MagicMock() for _ in range(25)]

        self.timezone_patcher = patch("training.tasks.timezone.now")
        mock_now = self.timezone_patcher.start()
        mock_now.return_value = timezone.datetime(2024, 1, 1, 12, 0, 0)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.BASE_DIR, ignore_errors=True)
        super().tearDownClass()

    def tearDown(self):
        self.collect_patcher.stop()
        self.build_pipeline_patcher.stop()
        self.prepare_examples_patcher.stop()
        self.timezone_patcher.stop()

    def test_train_model_aborts_if_not_enough_data(self):
        """Test that training aborts if there are fewer than 25 examples."""
        self.mock_collect.return_value = (self.mock_train_data[:10], [], [])
        train_model(source="both")
        self.assertEqual(Model.objects.count(), 1)  # Only the default model

    def test_train_model_successful_run(self):
        """Test a full, successful training run with mocks."""
        Model.objects.create(name="active_model", path="/fake/path", is_active=True)

        train_model(source="both", user=self.user)

        # Verify _build_spancat_pipeline was called
        self.mock_build_pipeline.assert_called_once()

        # Verify nlp.initialize was called
        self.mock_nlp.initialize.assert_called_once()

        # Verify training loop ran (nlp.update was called)
        self.assertTrue(self.mock_nlp.update.called)

        # Verify model was saved to disk
        self.assertTrue(self.mock_nlp.to_disk.called)

        self.assertEqual(Model.objects.count(), 3)  # Default + active + new
        new_model = Model.objects.get(name__startswith="model_both_")
        self.assertEqual(new_model.name, "model_both_20240101_120000")
        self.assertEqual(new_model.precision, 0.9)
        self.assertEqual(new_model.recall, 0.85)
        self.assertEqual(new_model.f1_score, 0.875)
        self.assertFalse(new_model.is_active)

        self.assertEqual(TrainingRun.objects.count(), 1)
        run = TrainingRun.objects.first()
        self.assertEqual(run.model, new_model)
        self.assertEqual(run.source, "both")

        self.assertEqual(run.trainingruntrainingdoc_set.count(), 2)
        self.assertEqual(run.trainingruncasedoc_set.count(), 2)

        for tdoc in self.used_tdocs:
            tdoc.refresh_from_db()
            self.assertTrue(tdoc.processed)

    def test_train_model_always_uses_en_core_web_lg(self):
        """Test that _build_spancat_pipeline is always called (uses en_core_web_lg internally)."""
        # No active model exists
        train_model(source="redactions")
        self.mock_build_pipeline.assert_called_once()

    def test_train_model_calls_update(self):
        """Test that nlp.update is called during training."""
        train_model(source="redactions")
        self.assertTrue(self.mock_nlp.update.called)

    def test_train_model_adds_custom_labels(self):
        """Test that THIRD_PARTY and OPERATIONAL labels are added via _build_spancat_pipeline."""
        # Stop the class-level mock so we can test the real function
        self.build_pipeline_patcher.stop()

        try:
            with patch("spacy.load") as mock_load:
                mock_base_nlp = MagicMock()
                # pipe_names needs to be a real list so list() iteration works
                pipe_names_list = ["tok2vec", "tagger", "parser", "ner"]
                type(mock_base_nlp).pipe_names = property(lambda self: list(pipe_names_list))

                def mock_remove_pipe(name):
                    pipe_names_list.remove(name)

                mock_base_nlp.remove_pipe.side_effect = mock_remove_pipe

                mock_tok2vec = MagicMock()
                mock_tok2vec.model.get_dim.return_value = 96
                mock_base_nlp.get_pipe.return_value = mock_tok2vec

                mock_spancat = MagicMock()
                mock_base_nlp.add_pipe.return_value = mock_spancat

                mock_load.return_value = mock_base_nlp

                from ..tasks import _build_spancat_pipeline

                _build_spancat_pipeline()

                # Verify en_core_web_lg was loaded
                mock_load.assert_called_once_with("en_core_web_lg")

                # Verify non-tok2vec pipes were removed
                self.assertEqual(mock_base_nlp.remove_pipe.call_count, 3)

                # Verify labels were added
                mock_spancat.add_label.assert_any_call("THIRD_PARTY")
                mock_spancat.add_label.assert_any_call("OPERATIONAL")
                self.assertEqual(mock_spancat.add_label.call_count, 2)
        finally:
            # Restart the patcher for tearDown
            self.build_pipeline_patcher = patch("training.tasks._build_spancat_pipeline")
            self.mock_build_pipeline = self.build_pipeline_patcher.start()
            self.mock_build_pipeline.return_value = self.mock_nlp
