import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from cases.models import Case
from cases.models import Document as CaseDocument

from ..models import (
    CustomDenyListItem,
    CustomPattern,
    CustomRecognizer,
    Model,
    TrainingDocument,
    TrainingRun,
    TrainingRunCaseDoc,
    TrainingRunTrainingDoc,
)
from ..serializers import (
    CustomRecognizerSerializer,
    ModelSerializer,
    TrainingDocumentSerializer,
    TrainingRunSerializer,
)
from .base import NetworkBlockerMixin

User = get_user_model()

MEDIA_ROOT = tempfile.mkdtemp(prefix="test_serializers_media")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ModelSerializerTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        Model.objects.all().delete()

    def test_serializes_all_fields(self):
        model = Model.objects.create(
            name="test_model_v1",
            path="/path/to/model",
            is_active=True,
            precision=0.85,
            recall=0.80,
            f1_score=0.82,
        )
        data = ModelSerializer(model).data

        self.assertEqual(data["name"], "test_model_v1")
        self.assertEqual(data["path"], "/path/to/model")
        self.assertTrue(data["is_active"])
        self.assertAlmostEqual(data["precision"], 0.85)
        self.assertAlmostEqual(data["recall"], 0.80)
        self.assertAlmostEqual(data["f1_score"], 0.82)
        self.assertIn("id", data)
        self.assertIn("created_at", data)

    def test_read_only_fields_not_writable(self):
        model = Model.objects.create(
            name="test_model_v2",
            path="/path/to/model_v2",
        )
        serializer = ModelSerializer(
            model,
            data={"name": "new_name", "path": "new/path", "is_active": True},
        )
        serializer.is_valid(raise_exception=True)
        # path is read-only and must not appear in validated_data
        self.assertNotIn("path", serializer.validated_data)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class TrainingDocumentSerializerTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user("docuser", password="password")

    def test_created_by_username_is_read_only(self):
        doc = TrainingDocument.objects.create(
            name="Test Doc",
            original_file=SimpleUploadedFile("test.docx", b"content"),
            created_by=self.user,
        )
        data = TrainingDocumentSerializer(doc).data

        self.assertEqual(data["created_by_username"], "docuser")
        self.assertIn("id", data)
        self.assertIn("name", data)
        self.assertIn("processed", data)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class TrainingRunSerializerTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        Model.objects.all().delete()
        self.model = Model.objects.create(
            name="run_model",
            path="/path/to/run_model",
            f1_score=0.9,
            precision=0.8,
            recall=0.85,
        )
        self.run = TrainingRun.objects.create(
            model=self.model, source="redactions"
        )

    def test_get_training_documents_returns_linked_docs(self):
        user = User.objects.create_user("runuser", password="password")
        doc = TrainingDocument.objects.create(
            name="Run Doc",
            original_file=SimpleUploadedFile("run.docx", b"content"),
            created_by=user,
        )
        TrainingRunTrainingDoc.objects.create(
            training_run=self.run, document=doc
        )

        data = TrainingRunSerializer(self.run).data

        self.assertEqual(len(data["training_documents"]), 1)
        self.assertEqual(data["training_documents"][0]["name"], "Run Doc")

    def test_get_case_documents_returns_linked_docs(self):
        case = Case.objects.create(case_reference="SRL01")
        case_doc = CaseDocument.objects.create(
            case=case,
            extracted_text="Some text",
            status=CaseDocument.Status.COMPLETED,
        )
        TrainingRunCaseDoc.objects.create(
            training_run=self.run, document=case_doc
        )

        data = TrainingRunSerializer(self.run).data

        self.assertEqual(len(data["case_documents"]), 1)
        self.assertIn("case_id", data["case_documents"][0])

    def test_scores_sourced_from_model(self):
        data = TrainingRunSerializer(self.run).data

        self.assertAlmostEqual(data["f1_score"], 0.9)
        self.assertAlmostEqual(data["precision"], 0.8)
        self.assertAlmostEqual(data["recall"], 0.85)

    def test_model_name_field_present(self):
        data = TrainingRunSerializer(self.run).data

        self.assertEqual(data["model_name"], "run_model")
        self.assertIn("source", data)
        self.assertIn("created_at", data)


class CustomRecognizerSerializerTests(NetworkBlockerMixin, TestCase):
    def _make_recognizer(self, **kwargs):
        defaults = {
            "name": "Crime Ref Pattern",
            "entity_type": CustomRecognizer.EntityType.OPERATIONAL,
            "patterns": [
                {
                    "name": "crime_ref",
                    "regex": r"\d{2}/\d{4}/\d{2}",
                    "score": 0.9,
                }
            ],
            "deny_list": [],
        }
        defaults.update(kwargs)
        return defaults

    def test_create_with_patterns(self):
        data = self._make_recognizer()
        serializer = CustomRecognizerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        instance = serializer.save()

        self.assertIsInstance(instance, CustomRecognizer)
        self.assertEqual(instance.name, "Crime Ref Pattern")
        self.assertEqual(
            instance.entity_type, CustomRecognizer.EntityType.OPERATIONAL
        )
        self.assertTrue(instance.is_active)
        self.assertEqual(instance.patterns.count(), 1)
        self.assertEqual(instance.deny_list.count(), 0)

    def test_create_with_deny_list(self):
        data = self._make_recognizer(
            name="Known Names",
            entity_type=CustomRecognizer.EntityType.THIRD_PARTY,
            patterns=[],
            deny_list=[{"value": "John Smith"}, {"value": "Jane Doe"}],
        )
        serializer = CustomRecognizerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        instance = serializer.save()

        self.assertEqual(instance.deny_list.count(), 2)
        self.assertEqual(instance.patterns.count(), 0)

    def test_invalid_regex_rejected(self):
        data = self._make_recognizer(
            patterns=[{"name": "bad", "regex": r"[invalid", "score": 0.5}]
        )
        serializer = CustomRecognizerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("patterns", serializer.errors)

    def test_empty_patterns_and_deny_list_invalid(self):
        data = self._make_recognizer(patterns=[], deny_list=[])
        serializer = CustomRecognizerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_update_replaces_patterns(self):
        recognizer = CustomRecognizer.objects.create(
            name="Old Recognizer",
            entity_type=CustomRecognizer.EntityType.THIRD_PARTY,
        )
        CustomPattern.objects.create(
            recognizer=recognizer, regex=r"\d+", score=0.8
        )

        data = {
            "name": "Old Recognizer",
            "entity_type": CustomRecognizer.EntityType.THIRD_PARTY,
            "patterns": [{"name": "new_pat", "regex": r"\w+", "score": 0.9}],
            "deny_list": [],
        }
        serializer = CustomRecognizerSerializer(
            instance=recognizer, data=data, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        instance = serializer.save()

        self.assertEqual(instance.patterns.count(), 1)
        self.assertEqual(instance.patterns.first().regex, r"\w+")

    def test_serialized_output_includes_nested_data(self):
        recognizer = CustomRecognizer.objects.create(
            name="Test Recognizer",
            entity_type=CustomRecognizer.EntityType.THIRD_PARTY,
        )
        CustomPattern.objects.create(
            recognizer=recognizer, name="p1", regex=r"\d+", score=0.85
        )
        CustomDenyListItem.objects.create(recognizer=recognizer, value="foo")

        data = CustomRecognizerSerializer(instance=recognizer).data

        self.assertEqual(len(data["patterns"]), 1)
        self.assertEqual(data["patterns"][0]["regex"], r"\d+")
        self.assertEqual(len(data["deny_list"]), 1)
        self.assertEqual(data["deny_list"][0]["value"], "foo")
