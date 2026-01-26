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
from spacy.tokens import DocBin

from cases.models import Case, Redaction
from cases.models import Document as CaseDocument

from ..models import Model, TrainingDocument, TrainingRun
from ..tasks import (
    collect_training_data_detailed,
    export_spacy_data,
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
        self.assertEqual(annotations["entities"][0][2], "THIRD_PARTY_PII")
        self.assertEqual(annotations["entities"][1][2], "OPERATIONAL_DATA")

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
        self.assertEqual(label, Redaction.RedactionType.THIRD_PARTY_PII)

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
        self.assertEqual(label, "THIRD_PARTY_PII")

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


class ExportSpacyDataTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.train_data = [
            ("Who is John Smith?", {"entities": [(7, 17, "PERSON")]}),
            ("I like London.", {"entities": [(7, 13, "GPE")]}),
        ]
        self.temp_dir = tempfile.mkdtemp()
        self.train_path = Path(self.temp_dir) / "train.spacy"
        self.dev_path = Path(self.temp_dir) / "dev.spacy"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_creates_training_file_only(self):
        """Test that only a training file is created when split is 1.0."""
        export_spacy_data(self.train_data, self.train_path, self.dev_path, split=1.0)
        self.assertTrue(self.train_path.exists())
        self.assertFalse(self.dev_path.exists())

    def test_export_creates_dev_file_only(self):
        """Test that only a dev file is created when split is 0.0."""
        export_spacy_data(self.train_data, self.train_path, self.dev_path, split=0.0)
        self.assertFalse(self.train_path.exists())
        self.assertTrue(self.dev_path.exists())

    def test_export_data_integrity(self):
        """Test that the data in the created DocBin is correct."""
        export_spacy_data(self.train_data, self.train_path, self.dev_path, split=1.0)

        nlp = spacy.blank("en")
        db = DocBin().from_disk(self.train_path)
        docs = list(db.get_docs(nlp.vocab))

        self.assertEqual(len(docs), 2)
        # Order is shuffled, so we check content
        texts = {doc.text for doc in docs}
        self.assertEqual(texts, {"Who is John Smith?", "I like London."})

        for doc in docs:
            if "John Smith" in doc.text:
                self.assertEqual(len(doc.ents), 1)
                self.assertEqual(doc.ents[0].text, "John Smith")
                self.assertEqual(doc.ents[0].label_, "PERSON")
            elif "London" in doc.text:
                self.assertEqual(len(doc.ents), 1)
                self.assertEqual(doc.ents[0].text, "London")
                self.assertEqual(doc.ents[0].label_, "GPE")


@override_settings(
    BASE_DIR=Path(tempfile.mkdtemp(prefix="test_base_train")),
    # To prevent HIGHLIGHT_COLOR_TO_LABEL from being empty
    # due to it being defined at module level in tasks.py
    HIGHLIGHT_COLOR_TO_LABEL={
        "BRIGHT_GREEN": "THIRD_PARTY_PII",
        "TURQUOISE": "OPERATIONAL_DATA",
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

        self.export_patcher = patch("training.tasks.export_spacy_data")
        self.mock_export = self.export_patcher.start()

        self.subprocess_patcher = patch("training.tasks.subprocess.run")
        self.mock_subprocess = self.subprocess_patcher.start()

        self.spacy_load_patcher = patch("training.tasks.spacy.load")
        self.mock_spacy_load = self.spacy_load_patcher.start()
        mock_nlp = MagicMock()
        mock_nlp.evaluate.return_value = {"ents_p": 0.9, "ents_r": 0.85, "ents_f": 0.875}
        # This is needed for the nlp.evaluate() call.
        real_nlp = spacy.blank("en")
        mock_nlp.make_doc.side_effect = real_nlp.make_doc
        self.mock_spacy_load.return_value = mock_nlp

        self.log_patcher = patch("training.tasks.LogEntryManager.log_create")
        self.mock_log = self.log_patcher.start()

        self.timezone_patcher = patch("training.tasks.timezone.now")
        mock_now = self.timezone_patcher.start()
        mock_now.return_value = timezone.datetime(2024, 1, 1, 12, 0, 0)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.BASE_DIR, ignore_errors=True)
        super().tearDownClass()

    def tearDown(self):
        self.collect_patcher.stop()
        self.export_patcher.stop()
        self.subprocess_patcher.stop()
        self.spacy_load_patcher.stop()
        self.log_patcher.stop()
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

    def test_train_model_uses_fallback_base_model(self):
        """Test that it uses 'en_core_web_lg' if no active model exists."""
        train_model(source="redactions")
        cmd_args = self.mock_subprocess.call_args[0][0]
        self.assertIn("en_core_web_lg", cmd_args)

    def test_train_model_logs_on_training_docs_source(self):
        """Test that a log entry is created for 'training_docs' source."""
        # Reset mock for this specific test
        self.mock_log.reset_mock()

        train_model(source="training_docs", user=self.user)

        # Check if the specific log call we care about was made,
        # ignoring other automatic logs from auditlog.
        expected_call_found = any(
            call.kwargs.get("force_log") is True and "training" in call.kwargs.get("changes", {})
            for call in self.mock_log.call_args_list
        )
        self.assertTrue(expected_call_found, "Expected explicit training log was not created.")

        self.mock_log.reset_mock()
        train_model(source="redactions", user=self.user)
        expected_call_found = any("training" in call.kwargs.get("changes", {}) for call in self.mock_log.call_args_list)
        self.assertFalse(expected_call_found, "A training log was created for 'redactions' source.")
