import os
import shutil
import tempfile
import uuid
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase, override_settings

from training.tests.base import NetworkBlockerMixin

from ..models import Case, Document, Redaction, RedactionContext

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        """Set up test data and authenticate a user for all view tests."""
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client.force_authenticate(user=self.user)

        self.case = Case.objects.create(
            case_reference="250001",
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

    @patch("cases.models.async_task")
    def test_case_export_triggers_task(self, mock_async_task):
        """Test that the CaseExportView triggers a background task."""
        # Ensure the document is marked as completed
        self.document.status = Document.Status.COMPLETED
        self.document.save()

        mock_async_task.return_value = "test-task-id"
        url = reverse("case-export", kwargs={"case_id": self.case.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["task_id"], "test-task-id")

        mock_async_task.assert_called_once_with("cases.services.export_case_documents", self.case.id)
        self.case.refresh_from_db()
        self.assertEqual(self.case.export_status, Case.ExportStatus.PROCESSING)
        self.assertEqual(self.case.export_task_id, "test-task-id")

    def test_case_export_not_found(self):
        """Test CaseExportView with a non-existent case ID returns 404."""
        non_existent_uuid = uuid.uuid4()
        url = reverse("case-export", kwargs={"case_id": non_existent_uuid})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_case_export_no_documents(self):
        """Test that exporting a case with no documents returns 400."""
        empty_case = Case.objects.create(case_reference="EMPTY1", data_subject_name="Empty Case", created_by=self.user)
        url = reverse("case-export", kwargs={"case_id": empty_case.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_case_export_incomplete_documents(self):
        """Test that exporting a case with incomplete documents returns 400."""
        self.document.status = Document.Status.READY_FOR_REVIEW
        self.document.save()

        url = reverse("case-export", kwargs={"case_id": self.case.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_cases(self):
        """Test listing all cases."""
        url = reverse("case-list-create")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["case_reference"], "250001")

    def test_create_case(self):
        """Test creating a new case."""
        url = reverse("case-list-create")
        data = {
            "case_reference": "250002",
            "data_subject_name": "Jane Smith",
            "data_subject_dob": "1985-05-15",
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Case.objects.count(), 2)
        new_case = Case.objects.get(case_reference="250002")
        self.assertEqual(new_case.created_by, self.user)

    def test_create_case_invalid_data(self):
        """Test creating a case with invalid data fails."""
        url = reverse("case-list-create")
        # Missing required 'data_subject_name'
        data = {
            "case_reference": "250003",
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("data_subject_name", response.data)
        self.assertEqual(Case.objects.count(), 1)

    def test_retrieve_case_detail(self):
        """Test retrieving a single case's details."""
        url = reverse("case-detail", kwargs={"case_id": self.case.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.case.id))
        self.assertEqual(len(response.data["documents"]), 1)
        self.assertEqual(response.data["documents"][0]["id"], str(self.document.id))

    def test_update_case_detail(self):
        """Test updating a case."""
        url = reverse("case-detail", kwargs={"case_id": self.case.id})
        data = {"status": Case.Status.COMPLETED}
        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.Status.COMPLETED)

    def test_create_multiple_documents(self):
        """Test uploading multiple documents to a case."""
        url = reverse("document-list-create", kwargs={"case_id": self.case.id})
        file1 = SimpleUploadedFile("file1.txt", b"content1")
        file2 = SimpleUploadedFile("file2.txt", b"content2")

        # Note: In tests, getlist works on a key with multiple values
        data = {"original_file": [file1, file2]}
        response = self.client.post(url, data, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # 1 existing + 2 new
        self.assertEqual(self.case.documents.count(), 3)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["filename"], "file1.txt")

    def test_create_document_invalid_data(self):
        """
        Test that uploading a document with invalid data (e.g., missing file)
        returns a 400 error, as the view will reject it before serialization.
        """
        url = reverse("document-list-create", kwargs={"case_id": self.case.id})
        # Posting without any 'original_file' data
        data = {}
        response = self.client.post(url, data, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.case.documents.count(), 1)

    def test_create_document_no_files(self):
        """Test that uploading with no files returns a 400 error."""
        url = reverse("document-list-create", kwargs={"case_id": self.case.id})
        response = self.client.post(url, {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_document_detail(self):
        """Test retrieving a single document's details."""
        url = reverse("document-detail", kwargs={"document_id": self.document.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.document.id))
        self.assertEqual(os.path.basename(response.data["original_file"]), "document.pdf")

    def test_update_document_status(self):
        """Test updating a document's status."""
        url = reverse("document-detail", kwargs={"document_id": self.document.id})
        data = {"new_status": Document.Status.COMPLETED}
        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.COMPLETED)

    def test_delete_document(self):
        """Test deleting a document."""
        url = reverse("document-detail", kwargs={"document_id": self.document.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Document.objects.filter(id=self.document.id).exists())

    def test_retrieve_document_review(self):
        """Test the document review endpoint."""
        url = reverse(
            "document-review",
            kwargs={"case_id": self.case.id, "document_id": self.document.id},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.document.id))
        self.assertIn("extracted_text", response.data)
        self.assertEqual(len(response.data["redactions"]), 1)

    def test_list_redactions_for_document(self):
        """Test listing all redactions for a specific document."""
        url = reverse("redaction-list-create", kwargs={"document_id": self.document.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(self.redaction.id))

    def test_create_redaction_for_document(self):
        """Test creating a new manual redaction for a document."""
        url = reverse("redaction-list-create", kwargs={"document_id": self.document.id})
        data = {
            "document": self.document.id,
            "start_char": 0,
            "end_char": 4,
            "text": "This",
            "redaction_type": Redaction.RedactionType.OPERATIONAL_DATA,
            "is_suggestion": False,
            "is_accepted": True,
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.document.redactions.count(), 2)
        new_redaction = Redaction.objects.get(text="This")
        self.assertFalse(new_redaction.is_suggestion)
        self.assertTrue(new_redaction.is_accepted)

    def test_retrieve_redaction_detail(self):
        """Test retrieving a single redaction."""
        url = reverse("redaction-detail", kwargs={"pk": self.redaction.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.redaction.id))
        self.assertEqual(response.data["text"], "PII")

    def test_update_redaction(self):
        """Test updating a redaction (e.g., accepting a suggestion)."""
        url = reverse("redaction-detail", kwargs={"pk": self.redaction.id})
        data = {
            "is_accepted": True,
            "justification": "User accepted this suggestion.",
        }
        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.redaction.refresh_from_db()
        self.assertTrue(self.redaction.is_accepted)
        self.assertEqual(self.redaction.justification, "User accepted this suggestion.")

    def test_delete_redaction(self):
        """Test deleting a redaction."""
        url = reverse("redaction-detail", kwargs={"pk": self.redaction.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Redaction.objects.filter(id=self.redaction.id).exists())

    def test_create_redaction_context(self):
        """Test creating a context for a redaction."""
        url = reverse("redaction-context", kwargs={"redaction_id": self.redaction.id})
        data = {"text": "This is some context."}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["text"], "This is some context.")
        self.assertTrue(RedactionContext.objects.filter(redaction=self.redaction).exists())

    def test_update_redaction_context(self):
        """Test updating an existing context for a redaction."""
        # First, create a context
        RedactionContext.objects.create(redaction=self.redaction, text="Initial context.")

        url = reverse("redaction-context", kwargs={"redaction_id": self.redaction.id})
        data = {"text": "Updated context."}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["text"], "Updated context.")
        self.redaction.context.refresh_from_db()
        self.assertEqual(self.redaction.context.text, "Updated context.")

    def test_delete_redaction_context(self):
        """Test deleting an existing context for a redaction."""
        RedactionContext.objects.create(redaction=self.redaction, text="Context to be deleted.")
        self.assertTrue(RedactionContext.objects.filter(redaction=self.redaction).exists())

        url = reverse("redaction-context", kwargs={"redaction_id": self.redaction.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(RedactionContext.objects.filter(redaction=self.redaction).exists())

    @patch("cases.views.async_task")
    def test_resubmit_document_success(self, mock_async_task):
        """Test resubmitting a document in ERROR status."""
        self.document.status = Document.Status.ERROR
        self.document.save()

        url = reverse("document-resubmit", kwargs={"document_id": self.document.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.PROCESSING)
        mock_async_task.assert_called_once_with(
            "cases.services.process_document_and_create_redactions", self.document.id
        )

    @patch("cases.views.async_task")
    def test_resubmit_document_ready_status_success(self, mock_async_task):
        """Test resubmitting a document in READY status succeeds."""
        self.document.status = Document.Status.READY_FOR_REVIEW
        self.document.save()

        url = reverse("document-resubmit", kwargs={"document_id": self.document.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.PROCESSING)
        mock_async_task.assert_called_once_with(
            "cases.services.process_document_and_create_redactions", self.document.id
        )

    @patch("cases.views.async_task")
    def test_resubmit_document_wrong_status(self, mock_async_task):
        """Test resubmitting a document in COMPLETED status fails."""
        self.document.status = Document.Status.COMPLETED
        self.document.save()

        url = reverse("document-resubmit", kwargs={"document_id": self.document.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.COMPLETED)
        mock_async_task.assert_not_called()

    @patch("cases.views.async_task")
    def test_resubmit_document_deletes_redactions(self, mock_async_task):
        """Test that resubmitting a document deletes existing redactions."""
        self.document.status = Document.Status.READY_FOR_REVIEW
        self.document.save()

        # Verify redaction exists before resubmit
        self.assertEqual(self.document.redactions.count(), 1)

        url = reverse("document-resubmit", kwargs={"document_id": self.document.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify redactions are deleted
        self.assertEqual(self.document.redactions.count(), 0)

    def test_resubmit_document_not_found(self):
        """Test resubmitting a non-existent document returns 404."""
        non_existent_uuid = uuid.uuid4()
        url = reverse("document-resubmit", kwargs={"document_id": non_existent_uuid})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_processing_success(self):
        """Test cancelling a document that is currently processing."""
        self.document.status = Document.Status.PROCESSING
        self.document.processing_task_id = "test-task-id"
        self.document.save()

        url = reverse("document-cancel", kwargs={"document_id": self.document.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.UNPROCESSED)
        self.assertIsNone(self.document.processing_task_id)
        self.assertIsNone(self.document.extracted_text)
        self.assertEqual(self.document.extracted_tables, [])
        self.assertIsNone(self.document.extracted_structure)
        self.assertEqual(self.document.redactions.count(), 0)

    def test_cancel_processing_wrong_status(self):
        """Test cancelling a document that is not processing returns 400."""
        self.document.status = Document.Status.READY_FOR_REVIEW
        self.document.save()

        url = reverse("document-cancel", kwargs={"document_id": self.document.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.READY_FOR_REVIEW)

    def test_cancel_processing_not_found(self):
        """Test cancelling a non-existent document returns 404."""
        non_existent_uuid = uuid.uuid4()
        url = reverse("document-cancel", kwargs={"document_id": non_existent_uuid})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_processing_deletes_redactions(self):
        """Test that cancelling processing deletes any redactions created so far."""
        self.document.status = Document.Status.PROCESSING
        self.document.save()

        # Verify redaction exists before cancel
        self.assertEqual(self.document.redactions.count(), 1)

        url = reverse("document-cancel", kwargs={"document_id": self.document.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.document.redactions.count(), 0)

    @patch("cases.views.async_task")
    def test_resubmit_document_unprocessed_status_success(self, mock_async_task):
        """Test resubmitting a document in UNPROCESSED status succeeds."""
        self.document.status = Document.Status.UNPROCESSED
        self.document.save()

        url = reverse("document-resubmit", kwargs={"document_id": self.document.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.PROCESSING)
        mock_async_task.assert_called_once_with(
            "cases.services.process_document_and_create_redactions", self.document.id
        )

    def test_unauthenticated_access_fails(self):
        """Test that unauthenticated users receive a 403 Forbidden error for
        all views."""
        self.client.logout()

        endpoints = {
            "case-list-create": {"method": "get", "kwargs": {}},
            "case-detail": {"method": "get", "kwargs": {"case_id": self.case.id}},
            "case-export": {"method": "post", "kwargs": {"case_id": self.case.id}},
            "document-list-create": {
                "method": "get",
                "kwargs": {"case_id": self.case.id},
            },
            "document-detail": {
                "method": "get",
                "kwargs": {"document_id": self.document.id},
            },
            "redaction-list-create": {
                "method": "get",
                "kwargs": {"document_id": self.document.id},
            },
            "redaction-detail": {"method": "get", "kwargs": {"pk": self.redaction.id}},
            "document-resubmit": {"method": "post", "kwargs": {"document_id": self.document.id}},
            "document-cancel": {"method": "post", "kwargs": {"document_id": self.document.id}},
        }

        for name, details in endpoints.items():
            with self.subTest(view=name):
                url = reverse(name, kwargs=details["kwargs"])
                method = getattr(self.client, details["method"])
                response = method(url)
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_non_existent_resource_fails(self):
        """Test that accessing a non-existent resource returns a 404."""
        non_existent_uuid = uuid.uuid4()
        url = reverse("case-detail", kwargs={"case_id": non_existent_uuid})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
