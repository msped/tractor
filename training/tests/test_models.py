import shutil
import tempfile
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from cases.models import Case, Document as CaseDocument
from ..models import (
    Model,
    TrainingDocument,
    TrainingEntity,
    TrainingRun,
    TrainingRunCaseDoc,
    TrainingRunTrainingDoc,
)

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ModelModelTests(TestCase):
    def test_model_str(self):
        model_active = Model.objects.create(
            name="active_model", path="/path/to/active", is_active=True
        )
        self.assertEqual(str(model_active), "active_model (Active)")

        model_inactive = Model.objects.create(
            name="inactive_model", path="/path/to/inactive", is_active=False
        )
        self.assertEqual(str(model_inactive), "inactive_model (Inactive)")

    def test_single_active_model_constraint(self):
        model1 = Model.objects.create(
            name="model1", path="/path/to/model1", is_active=True
        )
        self.assertTrue(model1.is_active)

        model2 = Model.objects.create(
            name="model2", path="/path/to/model2", is_active=True
        )
        self.assertTrue(model2.is_active)

        model1.refresh_from_db()
        self.assertFalse(model1.is_active)

        model2.save()
        self.assertTrue(model2.is_active)
        model1.refresh_from_db()
        self.assertFalse(model1.is_active)

        Model.objects.create(
            name="model3", path="/path/to/model3", is_active=False)
        model2.refresh_from_db()
        self.assertTrue(model2.is_active)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class TrainingDocumentModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="password")

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_training_document_str(self):
        doc = TrainingDocument.objects.create(
            name="My Test Doc",
            original_file=SimpleUploadedFile("test.docx", b"content"),
            created_by=self.user,
        )
        self.assertEqual(str(doc), "TrainingDoc: My Test Doc")

    def test_training_document_creation(self):
        doc = TrainingDocument.objects.create(
            name="Another Test Doc",
            original_file=SimpleUploadedFile("another.docx", b"content"),
            created_by=self.user,
            processed=False,
        )
        self.assertEqual(doc.name, "Another Test Doc")
        self.assertEqual(doc.created_by, self.user)
        self.assertFalse(doc.processed)


class TrainingEntityModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="testuser", password="password")
        self.doc = TrainingDocument.objects.create(
            name="DocForEntities",
            original_file=SimpleUploadedFile("entities.docx", b"content"),
            created_by=user,
        )

    def test_training_entity_str(self):
        entity = TrainingEntity.objects.create(
            document=self.doc,
            start_char=0,
            end_char=10,
            label=TrainingEntity.EntityType.OPERATIONAL,
        )
        self.assertIn("OPERATIONAL: 0-10", str(entity))
        self.assertIn("(DocForEntities)", str(entity))


class TrainingRunModelTests(TestCase):
    def setUp(self):
        self.model = Model.objects.create(
            name="run_model", path="/path/to/run_model")
        self.case = Case.objects.create(case_reference="C01")
        self.case_doc = CaseDocument.objects.create(
            case=self.case, original_file=SimpleUploadedFile(
                "case.txt", b"content")
        )
        user = User.objects.create_user(
            username="testuser", password="password")
        self.training_doc = TrainingDocument.objects.create(
            name="Training Doc for Run",
            original_file=SimpleUploadedFile("training.docx", b"content"),
            created_by=user,
        )

    def test_training_run_str(self):
        run = TrainingRun.objects.create(
            model=self.model, source="redactions"
        )
        self.assertEqual(
            str(run), f"TrainingRun {run.id} -> {self.model.name}")

    def test_training_run_creation(self):
        run = TrainingRun.objects.create(model=self.model, source="both")
        self.assertEqual(run.model, self.model)
        self.assertEqual(run.source, "both")

    def test_training_run_training_doc_link(self):
        run = TrainingRun.objects.create(
            model=self.model, source="training_docs")
        link = TrainingRunTrainingDoc.objects.create(
            training_run=run, document=self.training_doc
        )
        self.assertEqual(link.training_run, run)
        self.assertEqual(link.document, self.training_doc)
        self.assertEqual(run.trainingruntrainingdoc_set.count(), 1)

    def test_training_run_case_doc_link(self):
        run = TrainingRun.objects.create(model=self.model, source="redactions")
        link = TrainingRunCaseDoc.objects.create(
            training_run=run, document=self.case_doc
        )
        self.assertEqual(link.training_run, run)
        self.assertEqual(link.document, self.case_doc)
        self.assertEqual(run.trainingruncasedoc_set.count(), 1)
