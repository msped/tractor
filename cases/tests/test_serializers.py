import os
import shutil
import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from freezegun import freeze_time

from training.tests.base import NetworkBlockerMixin

from ..models import Case, Document, Redaction, RedactionContext
from ..serializers import (
    CaseDetailSerializer,
    CaseSerializer,
    DocumentReviewSerializer,
    DocumentSerializer,
    RedactionContextSerializer,
    RedactionSerializer,
)

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SerializerTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        """Set up test data for all serializer tests."""
        self.user = User.objects.create_user(username="testuser", password="password")
        self.case = Case.objects.create(
            case_reference="202001",
            data_subject_name="John Doe",
            data_subject_dob=date(1990, 1, 1),
            created_by=self.user,
        )
        self.test_file = SimpleUploadedFile("document.pdf", b"This is a test file.", "application/pdf")
        self.document = Document.objects.create(
            case=self.case,
            original_file=self.test_file,
            extracted_text="This is the extracted text with PII.",
        )
        self.redaction = Redaction.objects.create(
            document=self.document,
            start_char=35,
            end_char=38,
            text="PII",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )

    def tearDown(self):
        """Clean up the temporary media directory."""
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_case_serializer_read(self):
        """Test serialization of a Case instance."""
        serializer = CaseSerializer(instance=self.case)
        data = serializer.data

        self.assertEqual(data["id"], str(self.case.id))
        self.assertEqual(data["case_reference"], "202001")
        self.assertEqual(data["data_subject_name"], "John Doe")
        self.assertEqual(data["status"], "OPEN")
        self.assertEqual(data["status_display"], "Open")
        self.assertEqual(data["created_by"], self.user.username)
        self.assertIn("created_at", data)
        self.assertIn("retention_review_date", data)

    def test_case_serializer_create(self):
        """Test deserialization and creation of a Case instance."""
        data = {
            "case_reference": "202002",
            "data_subject_name": "Jane Smith",
            "data_subject_dob": "1985-05-15",
        }
        serializer = CaseSerializer(data=data)
        self.assertTrue(serializer.is_valid(raise_exception=True))
        instance = serializer.save(created_by=self.user)

        self.assertEqual(instance.case_reference, "202002")
        self.assertEqual(instance.created_by, self.user)
        self.assertEqual(Case.objects.count(), 2)

    def test_document_serializer_read(self):
        """Test serialization of a Document instance."""
        serializer = DocumentSerializer(instance=self.document)
        data = serializer.data

        self.assertEqual(data["id"], str(self.document.id))
        self.assertEqual(data["filename"], self.document.filename)
        self.assertEqual(data["status"], "Processing")
        self.assertEqual(data["extracted_text"], self.document.extracted_text)
        self.assertIn("uploaded_at", data)
        self.assertIn("redactions", data)
        self.assertEqual(len(data["redactions"]), 1)
        self.assertEqual(data["redactions"][0]["text"], "PII")

    def test_document_serializer_create(self):
        """Test deserialization and creation of a Document instance."""
        new_file = SimpleUploadedFile("report.docx", b"Another file.")
        data = {"case": self.case.pk, "original_file": new_file}

        serializer = DocumentSerializer(data=data)
        self.assertTrue(serializer.is_valid(raise_exception=True))
        instance = serializer.save()

        self.assertIsInstance(instance, Document)
        self.assertEqual(Document.objects.count(), 2)
        self.assertEqual(instance.case, self.case)
        self.assertEqual(instance.filename, "report.docx")
        self.assertEqual(instance.file_type, ".docx")
        self.assertTrue(os.path.exists(instance.original_file.path))

    def test_document_serializer_update_status(self):
        """Test updating a Document's status via the serializer."""
        data = {"new_status": Document.Status.COMPLETED}
        serializer = DocumentSerializer(instance=self.document, data=data, partial=True)
        self.assertTrue(serializer.is_valid(raise_exception=True))
        instance = serializer.save()

        self.assertEqual(instance.status, Document.Status.COMPLETED)

    def test_case_detail_serializer_read(self):
        """Test serialization of a Case with its related documents."""
        # Add another document to the case for a more thorough test
        Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("doc2.txt", b"content"),
        )

        serializer = CaseDetailSerializer(instance=self.case)
        data = serializer.data

        self.assertEqual(data["id"], str(self.case.id))
        self.assertIn("documents", data)
        self.assertEqual(len(data["documents"]), 2)
        self.assertEqual(data["documents"][0]["filename"], self.document.filename)
        self.assertIn("export_status", data)
        self.assertIn("export_file", data)
        self.assertIn("export_task_id", data)

    def test_redaction_serializer_read(self):
        """Test serialization of a Redaction instance."""
        serializer = RedactionSerializer(instance=self.redaction)
        data = serializer.data

        self.assertEqual(data["id"], str(self.redaction.id))
        self.assertEqual(data["start_char"], 35)
        self.assertEqual(data["end_char"], 38)
        self.assertEqual(data["text"], "PII")
        self.assertEqual(data["redaction_type"], "PII")
        self.assertTrue(data["is_suggestion"])
        self.assertFalse(data["is_accepted"])
        self.assertIn("created_at", data)

    def test_redaction_serializer_create(self):
        """Test deserialization and creation of a Redaction instance."""
        data = {
            "document": self.document.pk,
            "start_char": 0,
            "end_char": 4,
            "text": "This",
            "redaction_type": Redaction.RedactionType.OPERATIONAL_DATA,
            "is_suggestion": False,
            "is_accepted": True,
            "justification": "Manual redaction.",
        }
        serializer = RedactionSerializer(data=data)
        self.assertTrue(serializer.is_valid(raise_exception=True))
        instance = serializer.save()

        self.assertEqual(Redaction.objects.count(), 2)
        self.assertEqual(instance.document, self.document)
        self.assertEqual(instance.text, "This")
        self.assertFalse(instance.is_suggestion)
        self.assertTrue(instance.is_accepted)
        self.assertEqual(instance.justification, "Manual redaction.")

    def test_redaction_serializer_update(self):
        """Test updating a Redaction instance."""
        data = {
            "is_accepted": True,
            "justification": "User accepted this suggestion.",
        }
        serializer = RedactionSerializer(instance=self.redaction, data=data, partial=True)
        self.assertTrue(serializer.is_valid(raise_exception=True))
        instance = serializer.save()

        self.assertTrue(instance.is_accepted)
        self.assertEqual(instance.justification, "User accepted this suggestion.")

    def test_document_review_serializer_read(self):
        """Test serialization for the document review view."""
        # Add another redaction for a more thorough test
        Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="This",
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
        )

        serializer = DocumentReviewSerializer(instance=self.document)
        data = serializer.data

        self.assertEqual(data["id"], str(self.document.id))
        self.assertEqual(data["case"], self.case.pk)
        self.assertEqual(data["filename"], self.document.filename)
        self.assertEqual(data["extracted_text"], self.document.extracted_text)
        self.assertIn("redactions", data)
        self.assertEqual(len(data["redactions"]), 2)

        # Check that fields not in the serializer are absent
        self.assertNotIn("status", data)
        self.assertNotIn("uploaded_at", data)
        self.assertNotIn("original_file", data)

    @freeze_time("2025-01-01")
    def test_case_serializer_fields(self):
        """Ensure all expected fields are present in CaseSerializer."""
        serializer = CaseSerializer(instance=self.case)
        expected_fields = {
            "id",
            "status",
            "status_display",
            "case_reference",
            "data_subject_name",
            "data_subject_dob",
            "created_at",
            "created_by",
            "retention_review_date",
        }
        self.assertEqual(set(serializer.data.keys()), expected_fields)

    def test_redaction_context_serializer_read(self):
        """Test serialization of a RedactionContext instance."""
        context = RedactionContext.objects.create(redaction=self.redaction, text="This is context.")
        serializer = RedactionContextSerializer(instance=context)
        data = serializer.data

        self.assertEqual(data["redaction"], self.redaction.id)
        self.assertEqual(data["text"], "This is context.")

    def test_redaction_context_serializer_create(self):
        """Test deserialization and creation of a RedactionContext."""
        data = {"text": "New context for redaction."}
        serializer = RedactionContextSerializer(data=data)
        self.assertTrue(serializer.is_valid(raise_exception=True))

        instance = serializer.save(redaction=self.redaction)

        self.assertEqual(RedactionContext.objects.count(), 1)
        self.assertEqual(instance.redaction, self.redaction)
        self.assertEqual(instance.text, "New context for redaction.")

    def test_redaction_serializer_includes_context(self):
        """
        Test that the RedactionSerializer correctly includes the nested
        RedactionContext data when it exists.
        """
        serializer_no_context = RedactionSerializer(instance=self.redaction)
        self.assertIsNone(serializer_no_context.data["context"])

        RedactionContext.objects.create(redaction=self.redaction, text="This is important context.")
        self.redaction.refresh_from_db()

        serializer_with_context = RedactionSerializer(instance=self.redaction)
        context_data = serializer_with_context.data["context"]
        self.assertIsNotNone(context_data)
        self.assertEqual(context_data["text"], "This is important context.")
