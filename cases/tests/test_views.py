import io
import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase, override_settings

from training.tests.base import NetworkBlockerMixin

from ..models import (
    Case,
    Document,
    DocumentExportSettings,
    ExemptionTemplate,
    Export,
    InternalReview,
    Redaction,
    RedactionContext,
)

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


def _make_docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "")
    return buf.getvalue()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        """Set up test data and authenticate a user for all view tests."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="password"
        )
        self.client.force_authenticate(user=self.user)

        self.case = Case.objects.create(
            case_reference="250001",
            data_subject_name="John Doe",
            data_subject_dob=date(1990, 1, 1),
            created_by=self.user,
        )
        self.test_file = SimpleUploadedFile(
            "document.pdf", b"This is a test file.", "application/pdf"
        )
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

        mock_async_task.assert_called_once_with(
            "cases.tasks.export_case_documents", self.case.id, None
        )
        self.case.refresh_from_db()
        self.assertEqual(self.case.export_status, Case.ExportStatus.PROCESSING)
        self.assertEqual(self.case.export_task_id, "test-task-id")

    @patch("cases.models.async_task")
    def test_case_export_already_processing_returns_409(self, mock_async_task):
        """A second export request while one is running must not enqueue."""
        self.document.status = Document.Status.COMPLETED
        self.document.save()
        self.case.export_status = Case.ExportStatus.PROCESSING
        self.case.save()

        url = reverse("case-export", kwargs={"case_id": self.case.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        mock_async_task.assert_not_called()

    def test_case_export_not_found(self):
        """Test CaseExportView with a non-existent case ID returns 404."""
        non_existent_uuid = uuid.uuid4()
        url = reverse("case-export", kwargs={"case_id": non_existent_uuid})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_case_export_no_documents(self):
        """Test that exporting a case with no documents returns 400."""
        empty_case = Case.objects.create(
            case_reference="EMPTY1",
            data_subject_name="Empty Case",
            created_by=self.user,
        )
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
        """Test listing cases returns paginated response."""
        url = reverse("case-list-create")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["case_reference"], "250001"
        )

    def test_list_cases_search_by_reference(self):
        url = reverse("case-list-create")
        response = self.client.get(url, {"search": "250001"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_list_cases_search_no_match(self):
        url = reverse("case-list-create")
        response = self.client.get(url, {"search": "XXXXXX"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_list_cases_status_filter(self):
        url = reverse("case-list-create")
        response = self.client.get(url, {"status": "OPEN"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_list_cases_status_filter_no_match(self):
        url = reverse("case-list-create")
        response = self.client.get(url, {"status": "COMPLETED"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_list_cases_ordered_newest_first(self):
        Case.objects.create(
            case_reference="250002",
            data_subject_name="Second Case",
            created_by=self.user,
        )
        url = reverse("case-list-create")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0]["case_reference"], "250002"
        )

    def test_list_cases_pagination(self):
        for i in range(2, 15):
            Case.objects.create(
                case_reference=f"2500{i:02d}",
                data_subject_name=f"Subject {i}",
                created_by=self.user,
            )
        url = reverse("case-list-create")
        response = self.client.get(url, {"page": 1, "page_size": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["next"])

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
        self.assertEqual(
            response.data["documents"][0]["id"], str(self.document.id)
        )

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
        docx_bytes = _make_docx_bytes()
        file1 = SimpleUploadedFile("file1.docx", docx_bytes)
        file2 = SimpleUploadedFile("file2.docx", docx_bytes)

        # Note: In tests, getlist works on a key with multiple values
        data = {"original_file": [file1, file2]}
        response = self.client.post(url, data, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # 1 existing + 2 new
        self.assertEqual(self.case.documents.count(), 3)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["filename"], "file1.docx")

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
        url = reverse(
            "document-detail", kwargs={"document_id": self.document.id}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.document.id))
        self.assertEqual(
            os.path.basename(response.data["original_file"]), "document.pdf"
        )

    def test_update_document_status(self):
        """Test updating a document's status."""
        url = reverse(
            "document-detail", kwargs={"document_id": self.document.id}
        )
        data = {"new_status": Document.Status.COMPLETED}
        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.COMPLETED)

    def test_delete_document(self):
        """Test deleting a document."""
        url = reverse(
            "document-detail", kwargs={"document_id": self.document.id}
        )
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
        url = reverse(
            "redaction-list-create", kwargs={"document_id": self.document.id}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(self.redaction.id))

    def test_create_redaction_for_document(self):
        """Test creating a new manual redaction for a document."""
        url = reverse(
            "redaction-list-create", kwargs={"document_id": self.document.id}
        )
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
        self.assertEqual(
            self.redaction.justification, "User accepted this suggestion."
        )

    def test_delete_redaction(self):
        """Test deleting a redaction."""
        url = reverse("redaction-detail", kwargs={"pk": self.redaction.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Redaction.objects.filter(id=self.redaction.id).exists()
        )

    def test_create_redaction_context(self):
        """Test creating a context for a redaction."""
        url = reverse(
            "redaction-context", kwargs={"redaction_id": self.redaction.id}
        )
        data = {"text": "This is some context."}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["text"], "This is some context.")
        self.assertTrue(
            RedactionContext.objects.filter(redaction=self.redaction).exists()
        )

    def test_update_redaction_context(self):
        """Test updating an existing context for a redaction."""
        # First, create a context
        RedactionContext.objects.create(
            redaction=self.redaction, text="Initial context."
        )

        url = reverse(
            "redaction-context", kwargs={"redaction_id": self.redaction.id}
        )
        data = {"text": "Updated context."}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["text"], "Updated context.")
        self.redaction.context.refresh_from_db()
        self.assertEqual(self.redaction.context.text, "Updated context.")

    def test_delete_redaction_context(self):
        """Test deleting an existing context for a redaction."""
        RedactionContext.objects.create(
            redaction=self.redaction, text="Context to be deleted."
        )
        self.assertTrue(
            RedactionContext.objects.filter(redaction=self.redaction).exists()
        )

        url = reverse(
            "redaction-context", kwargs={"redaction_id": self.redaction.id}
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            RedactionContext.objects.filter(redaction=self.redaction).exists()
        )

    @patch("cases.models.async_task")
    def test_resubmit_document_success(self, mock_async_task):
        """Test resubmitting a document in ERROR status."""
        mock_async_task.return_value = "test-task-id"
        self.document.status = Document.Status.ERROR
        self.document.save()

        url = reverse(
            "document-resubmit", kwargs={"document_id": self.document.id}
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.PROCESSING)
        mock_async_task.assert_called_once_with(
            "cases.tasks.process_document_and_create_redactions",
            self.document.id,
        )

    @patch("cases.models.async_task")
    def test_resubmit_document_ready_status_success(self, mock_async_task):
        """Test resubmitting a document in READY status succeeds."""
        mock_async_task.return_value = "test-task-id"
        self.document.status = Document.Status.READY_FOR_REVIEW
        self.document.save()

        url = reverse(
            "document-resubmit", kwargs={"document_id": self.document.id}
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.PROCESSING)
        mock_async_task.assert_called_once_with(
            "cases.tasks.process_document_and_create_redactions",
            self.document.id,
        )

    @patch("cases.models.async_task")
    def test_resubmit_document_wrong_status(self, mock_async_task):
        """Test resubmitting a document in COMPLETED status fails."""
        self.document.status = Document.Status.COMPLETED
        self.document.save()

        url = reverse(
            "document-resubmit", kwargs={"document_id": self.document.id}
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.COMPLETED)
        mock_async_task.assert_not_called()

    @patch("cases.models.async_task")
    def test_resubmit_document_deletes_redactions(self, mock_async_task):
        """Test that resubmitting a document deletes existing redactions."""
        mock_async_task.return_value = "test-task-id"
        self.document.status = Document.Status.READY_FOR_REVIEW
        self.document.save()

        # Verify redaction exists before resubmit
        self.assertEqual(self.document.redactions.count(), 1)

        url = reverse(
            "document-resubmit", kwargs={"document_id": self.document.id}
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify redactions are deleted
        self.assertEqual(self.document.redactions.count(), 0)

    def test_resubmit_document_not_found(self):
        """Test resubmitting a non-existent document returns 404."""
        non_existent_uuid = uuid.uuid4()
        url = reverse(
            "document-resubmit", kwargs={"document_id": non_existent_uuid}
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_processing_success(self):
        """Test cancelling a document that is currently processing."""
        self.document.status = Document.Status.PROCESSING
        self.document.processing_task_id = "test-task-id"
        self.document.save()

        url = reverse(
            "document-cancel", kwargs={"document_id": self.document.id}
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.UNPROCESSED)
        self.assertIsNone(self.document.processing_task_id)
        self.assertIsNone(self.document.extracted_text)
        self.assertEqual(self.document.extracted_tables, [])
        self.assertIsNone(self.document.extracted_structure)
        self.assertEqual(self.document.redactions.count(), 0)

    def test_cancel_processing_dequeues_task(self):
        """Cancelling removes the queued django-q task from the broker."""
        from django_q.models import OrmQ
        from django_q.tasks import async_task

        OrmQ.objects.all().delete()
        task_id = async_task(
            "cases.tasks.process_document_and_create_redactions",
            self.document.id,
        )
        self.document.status = Document.Status.PROCESSING
        self.document.processing_task_id = task_id
        self.document.save()
        self.assertTrue(
            any(q.task_id() == task_id for q in OrmQ.objects.all())
        )

        url = reverse(
            "document-cancel", kwargs={"document_id": self.document.id}
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            any(q.task_id() == task_id for q in OrmQ.objects.all())
        )

    def test_cancel_processing_wrong_status(self):
        """Test cancelling a document that is not processing returns 400."""
        self.document.status = Document.Status.READY_FOR_REVIEW
        self.document.save()

        url = reverse(
            "document-cancel", kwargs={"document_id": self.document.id}
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.document.refresh_from_db()
        self.assertEqual(
            self.document.status, Document.Status.READY_FOR_REVIEW
        )

    def test_cancel_processing_not_found(self):
        """Test cancelling a non-existent document returns 404."""
        non_existent_uuid = uuid.uuid4()
        url = reverse(
            "document-cancel", kwargs={"document_id": non_existent_uuid}
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_processing_deletes_redactions(self):
        """Test that cancelling processing deletes any redactions created so far."""
        self.document.status = Document.Status.PROCESSING
        self.document.save()

        # Verify redaction exists before cancel
        self.assertEqual(self.document.redactions.count(), 1)

        url = reverse(
            "document-cancel", kwargs={"document_id": self.document.id}
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.document.redactions.count(), 0)

    @patch("cases.models.async_task")
    def test_resubmit_document_unprocessed_status_success(
        self, mock_async_task
    ):
        """Test resubmitting a document in UNPROCESSED status succeeds."""
        mock_async_task.return_value = "test-task-id"
        self.document.status = Document.Status.UNPROCESSED
        self.document.save()

        url = reverse(
            "document-resubmit", kwargs={"document_id": self.document.id}
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.PROCESSING)
        mock_async_task.assert_called_once_with(
            "cases.tasks.process_document_and_create_redactions",
            self.document.id,
        )

    def test_unauthenticated_access_fails(self):
        """Test that unauthenticated users receive a 403 Forbidden error for
        all views."""
        self.client.logout()

        endpoints = {
            "case-list-create": {"method": "get", "kwargs": {}},
            "case-detail": {
                "method": "get",
                "kwargs": {"case_id": self.case.id},
            },
            "case-export": {
                "method": "post",
                "kwargs": {"case_id": self.case.id},
            },
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
            "redaction-detail": {
                "method": "get",
                "kwargs": {"pk": self.redaction.id},
            },
            "document-resubmit": {
                "method": "post",
                "kwargs": {"document_id": self.document.id},
            },
            "document-cancel": {
                "method": "post",
                "kwargs": {"document_id": self.document.id},
            },
            "exemption-template-list": {"method": "get", "kwargs": {}},
        }

        for name, details in endpoints.items():
            with self.subTest(view=name):
                url = reverse(name, kwargs=details["kwargs"])
                method = getattr(self.client, details["method"])
                response = method(url)
                self.assertEqual(
                    response.status_code, status.HTTP_401_UNAUTHORIZED
                )

    def test_access_non_existent_resource_fails(self):
        """Test that accessing a non-existent resource returns a 404."""
        non_existent_uuid = uuid.uuid4()
        url = reverse("case-detail", kwargs={"case_id": non_existent_uuid})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class BulkRedactionUpdateViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="bulkuser", password="password"
        )
        self.client.force_authenticate(user=self.user)

        self.case = Case.objects.create(
            case_reference="BULK01",
            data_subject_name="Bulk Test",
            created_by=self.user,
        )
        test_file = SimpleUploadedFile(
            "bulk.pdf", b"bulk content", "application/pdf"
        )
        self.document = Document.objects.create(
            case=self.case, original_file=test_file
        )
        self.r1 = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=3,
            text="PII",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        self.r2 = Redaction.objects.create(
            document=self.document,
            start_char=4,
            end_char=8,
            text="data",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_bulk_accept_redactions(self):
        """Test accepting multiple redactions in a single request."""
        url = reverse(
            "bulk-redaction-update", kwargs={"document_id": self.document.id}
        )
        data = {"ids": [str(self.r1.id), str(self.r2.id)], "is_accepted": True}
        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.r1.refresh_from_db()
        self.r2.refresh_from_db()
        self.assertTrue(self.r1.is_accepted)
        self.assertTrue(self.r2.is_accepted)

    def test_bulk_reject_with_justification(self):
        """Test rejecting multiple redactions with a shared justification."""
        url = reverse(
            "bulk-redaction-update", kwargs={"document_id": self.document.id}
        )
        data = {
            "ids": [str(self.r1.id), str(self.r2.id)],
            "is_accepted": False,
            "justification": "Bulk rejection reason",
        }
        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.r1.refresh_from_db()
        self.r2.refresh_from_db()
        self.assertEqual(self.r1.justification, "Bulk rejection reason")
        self.assertEqual(self.r2.justification, "Bulk rejection reason")

    def test_bulk_update_filters_by_document(self):
        """Redactions belonging to a different document are not updated."""
        other_file = SimpleUploadedFile(
            "other.pdf", b"other", "application/pdf"
        )
        other_doc = Document.objects.create(
            case=self.case, original_file=other_file
        )
        other_r = Redaction.objects.create(
            document=other_doc,
            start_char=0,
            end_char=3,
            text="PII",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )

        url = reverse(
            "bulk-redaction-update", kwargs={"document_id": self.document.id}
        )
        data = {"ids": [str(other_r.id)], "is_accepted": True}
        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        other_r.refresh_from_db()
        self.assertFalse(other_r.is_accepted)

    def test_bulk_update_empty_ids(self):
        """An empty ids list returns an empty 200 response."""
        url = reverse(
            "bulk-redaction-update", kwargs={"document_id": self.document.id}
        )
        data = {"ids": [], "is_accepted": True}
        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_bulk_update_missing_is_accepted_returns_400(self):
        """Omitting is_accepted must 400, not 500 on a null DB update."""
        url = reverse(
            "bulk-redaction-update", kwargs={"document_id": self.document.id}
        )
        response = self.client.patch(
            url, {"ids": [str(self.r1.id)]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.r1.refresh_from_db()
        self.assertFalse(self.r1.is_accepted)

    def test_bulk_update_invalid_ids_returns_400(self):
        """Non-UUID ids are rejected by validation."""
        url = reverse(
            "bulk-redaction-update", kwargs={"document_id": self.document.id}
        )
        response = self.client.patch(
            url, {"ids": ["not-a-uuid"], "is_accepted": True}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_update_unauthenticated(self):
        """Unauthenticated requests are rejected."""
        self.client.logout()
        url = reverse(
            "bulk-redaction-update", kwargs={"document_id": self.document.id}
        )
        response = self.client.patch(
            url, {"ids": [], "is_accepted": True}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ExemptionTemplateViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="exemptuser", password="password"
        )
        self.client.force_authenticate(user=self.user)
        admin = User.objects.create_superuser(
            username="exemptadmin", password="password"
        )
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=admin)

        self.active = ExemptionTemplate.objects.create(
            name="S.40 - Personal Information", is_active=True
        )
        self.inactive = ExemptionTemplate.objects.create(
            name="S.41 - Deprecated", is_active=False
        )

    def test_list_returns_only_active_templates(self):
        """GET returns only active templates."""
        url = reverse("exemption-template-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [t["name"] for t in response.data]
        self.assertIn("S.40 - Personal Information", names)
        self.assertNotIn("S.41 - Deprecated", names)

    def test_list_returns_expected_fields(self):
        """GET response includes id, name, and description."""
        url = reverse("exemption-template-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data[0]
        self.assertIn("id", item)
        self.assertIn("name", item)
        self.assertIn("description", item)

    def test_create_exemption_template(self):
        """POST by admin creates a new active template."""
        url = reverse("exemption-template-list")
        data = {
            "name": "S.42 - Legal Privilege",
            "description": "Legal advice exemption",
        }
        response = self.admin_client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "S.42 - Legal Privilege")
        self.assertEqual(
            response.data["description"], "Legal advice exemption"
        )
        self.assertTrue(
            ExemptionTemplate.objects.filter(
                name="S.42 - Legal Privilege"
            ).exists()
        )

    def test_create_forbidden_for_non_admin(self):
        """POST by a regular user is rejected with 403."""
        url = reverse("exemption-template-list")
        response = self.client.post(url, {"name": "S.42 - Legal Privilege"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_duplicate_name_fails(self):
        """POST with a duplicate name returns 400."""
        url = reverse("exemption-template-list")
        data = {"name": "S.40 - Personal Information"}
        response = self.admin_client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_create_missing_name_fails(self):
        """POST without a name returns 400."""
        url = reverse("exemption-template-list")
        response = self.admin_client.post(url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_exemption_template(self):
        """DELETE removes the template (admin only)."""
        url = reverse(
            "exemption-template-detail", kwargs={"pk": self.active.pk}
        )
        response = self.admin_client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            ExemptionTemplate.objects.filter(pk=self.active.pk).exists()
        )

    def test_delete_exemption_template_forbidden_for_non_admin(self):
        """DELETE is forbidden for non-admin users."""
        url = reverse(
            "exemption-template-detail", kwargs={"pk": self.active.pk}
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_nonexistent_template_returns_404(self):
        """DELETE on a non-existent pk returns 404."""
        url = reverse("exemption-template-detail", kwargs={"pk": 99999})
        response = self.admin_client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_unauthenticated(self):
        """Unauthenticated GET is rejected."""
        self.client.logout()
        url = reverse("exemption-template-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_unauthenticated(self):
        """Unauthenticated POST is rejected."""
        self.client.logout()
        url = reverse("exemption-template-list")
        response = self.client.post(url, {"name": "S.99"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_unauthenticated(self):
        """Unauthenticated DELETE is rejected."""
        self.client.logout()
        url = reverse(
            "exemption-template-detail", kwargs={"pk": self.active.pk}
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ExportSettingsViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin", password="password"
        )
        self.user = User.objects.create_user(
            username="regularuser", password="password"
        )
        self.url = reverse("export-settings")

    def test_admin_get_returns_default_values(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["header_text"], "")
        self.assertEqual(response.data["footer_text"], "")
        self.assertEqual(response.data["watermark_text"], "")
        self.assertFalse(response.data["watermark_include_case_ref"])
        self.assertFalse(response.data["page_numbers_enabled"])

    def test_admin_patch_updates_and_returns_new_values(self):
        self.client.force_authenticate(user=self.admin)
        payload = {"header_text": "OFFICIAL", "page_numbers_enabled": True}
        response = self.client.patch(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["header_text"], "OFFICIAL")
        self.assertTrue(response.data["page_numbers_enabled"])
        obj = DocumentExportSettings.get()
        self.assertEqual(obj.header_text, "OFFICIAL")
        self.assertTrue(obj.page_numbers_enabled)

    def test_non_admin_receives_403(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_receives_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class BulkByTextRedactionViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="bytext_user", password="password"
        )
        self.client.force_authenticate(user=self.user)

        self.case = Case.objects.create(
            case_reference="BT01",
            data_subject_name="By Text Test",
            created_by=self.user,
        )
        file1 = SimpleUploadedFile("doc1.pdf", b"content1", "application/pdf")
        file2 = SimpleUploadedFile("doc2.pdf", b"content2", "application/pdf")
        self.doc1 = Document.objects.create(
            case=self.case, original_file=file1
        )
        self.doc2 = Document.objects.create(
            case=self.case, original_file=file2
        )

        # Two pending redactions matching the target text, one in each document
        self.r1 = Redaction.objects.create(
            document=self.doc1,
            start_char=0,
            end_char=8,
            text="John Doe",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        self.r2 = Redaction.objects.create(
            document=self.doc2,
            start_char=5,
            end_char=13,
            text="John Doe",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        # Already accepted — must not be touched
        self.r_accepted = Redaction.objects.create(
            document=self.doc1,
            start_char=10,
            end_char=18,
            text="John Doe",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        # Already rejected — must not be touched
        self.r_rejected = Redaction.objects.create(
            document=self.doc1,
            start_char=20,
            end_char=28,
            text="John Doe",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            justification="Previously reviewed",
            decided_by=Redaction.DecidedBy.HUMAN,
        )

    def tearDown(self):
        import shutil

        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _url(self):
        return reverse(
            "bulk-by-text-redaction-update", kwargs={"case_id": self.case.id}
        )

    def test_accept_updates_all_pending_and_returns_count(self):
        response = self.client.post(
            self._url(),
            {
                "text": "John Doe",
                "redaction_type": "PII",
                "status": "ACCEPTED",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated"], 2)
        self.r1.refresh_from_db()
        self.r2.refresh_from_db()
        self.assertTrue(self.r1.is_accepted)
        self.assertTrue(self.r2.is_accepted)

    def test_reject_updates_all_pending_with_reason(self):
        response = self.client.post(
            self._url(),
            {
                "text": "John Doe",
                "redaction_type": "PII",
                "status": "REJECTED",
                "rejection_reason": "Not relevant",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated"], 2)
        self.r1.refresh_from_db()
        self.r2.refresh_from_db()
        self.assertFalse(self.r1.is_accepted)
        self.assertEqual(self.r1.justification, "Not relevant")
        self.assertFalse(self.r2.is_accepted)
        self.assertEqual(self.r2.justification, "Not relevant")

    def test_already_accepted_redactions_not_modified(self):
        self.client.post(
            self._url(),
            {
                "text": "John Doe",
                "redaction_type": "PII",
                "status": "ACCEPTED",
            },
            format="json",
        )
        self.r_accepted.refresh_from_db()
        # is_accepted stays True, no double-counting
        self.assertTrue(self.r_accepted.is_accepted)

    def test_already_rejected_redactions_not_modified(self):
        original_justification = self.r_rejected.justification
        self.client.post(
            self._url(),
            {
                "text": "John Doe",
                "redaction_type": "PII",
                "status": "ACCEPTED",
            },
            format="json",
        )
        self.r_rejected.refresh_from_db()
        self.assertFalse(self.r_rejected.is_accepted)
        self.assertEqual(self.r_rejected.justification, original_justification)

    def test_redactions_in_other_case_not_affected(self):
        other_case = Case.objects.create(
            case_reference="BT02",
            data_subject_name="Other Subject",
            created_by=self.user,
        )
        other_file = SimpleUploadedFile("other.pdf", b"x", "application/pdf")
        other_doc = Document.objects.create(
            case=other_case, original_file=other_file
        )
        other_r = Redaction.objects.create(
            document=other_doc,
            start_char=0,
            end_char=8,
            text="John Doe",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )

        self.client.post(
            self._url(),
            {
                "text": "John Doe",
                "redaction_type": "PII",
                "status": "ACCEPTED",
            },
            format="json",
        )
        other_r.refresh_from_db()
        self.assertFalse(other_r.is_accepted)

    def test_invalid_payload_returns_400(self):
        response = self.client.post(
            self._url(),
            {
                "text": "John Doe",
                "redaction_type": "INVALID",
                "status": "ACCEPTED",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            self._url(),
            {
                "text": "John Doe",
                "redaction_type": "PII",
                "status": "ACCEPTED",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(
    MEDIA_ROOT=MEDIA_ROOT,
    AUTO_CASE_DELETION_ENABLED=False,
    RETENTION_WARNING_DAYS=30,
)
class RetentionViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="retentionadmin", password="password"
        )
        self.user = User.objects.create_user(
            username="retentionuser", password="password"
        )
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin)
        self.client.force_authenticate(user=self.user)

        today = date.today()
        self.past_case = Case.objects.create(
            case_reference="RET001",
            data_subject_name="Past Subject",
            created_by=self.admin,
            retention_review_date=today - timedelta(days=1),
        )
        self.upcoming_case = Case.objects.create(
            case_reference="RET002",
            data_subject_name="Upcoming Subject",
            created_by=self.admin,
            retention_review_date=today + timedelta(days=15),
        )
        self.future_case = Case.objects.create(
            case_reference="RET003",
            data_subject_name="Future Subject",
            created_by=self.admin,
            retention_review_date=today + timedelta(days=365),
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_get_returns_expected_structure(self):
        url = reverse("retention-settings")
        response = self.admin_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("auto_case_deletion_enabled", response.data)
        self.assertIn("retention_warning_days", response.data)
        self.assertIn("past", response.data)
        self.assertIn("upcoming", response.data)

    def test_past_cases_appear_in_past_list(self):
        url = reverse("retention-settings")
        response = self.admin_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        refs = [c["case_reference"] for c in response.data["past"]]
        self.assertIn("RET001", refs)
        self.assertNotIn("RET002", refs)
        self.assertNotIn("RET003", refs)

    def test_upcoming_cases_appear_in_upcoming_list(self):
        url = reverse("retention-settings")
        response = self.admin_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        refs = [c["case_reference"] for c in response.data["upcoming"]]
        self.assertIn("RET002", refs)
        self.assertNotIn("RET001", refs)
        self.assertNotIn("RET003", refs)

    def test_far_future_cases_not_in_either_list(self):
        url = reverse("retention-settings")
        response = self.admin_client.get(url)

        all_refs = [c["case_reference"] for c in response.data["past"]] + [
            c["case_reference"] for c in response.data["upcoming"]
        ]
        self.assertNotIn("RET003", all_refs)

    def test_non_admin_gets_403(self):
        url = reverse("retention-settings")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_gets_401(self):
        unauthenticated = APIClient()
        url = reverse("retention-settings")
        response = unauthenticated.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_bulk_delete_removes_cases(self):
        url = reverse("bulk-case-delete")
        response = self.admin_client.post(
            url,
            {"ids": [str(self.past_case.id)]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["deleted"], 1)
        self.assertFalse(Case.objects.filter(id=self.past_case.id).exists())

    def test_bulk_delete_multiple_cases(self):
        url = reverse("bulk-case-delete")
        response = self.admin_client.post(
            url,
            {"ids": [str(self.past_case.id), str(self.upcoming_case.id)]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["deleted"], 2)

    def test_bulk_delete_ignores_nonexistent_ids(self):
        url = reverse("bulk-case-delete")
        response = self.admin_client.post(
            url,
            {"ids": [str(uuid.uuid4())]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["deleted"], 0)

    def test_bulk_delete_empty_ids_returns_400(self):
        url = reverse("bulk-case-delete")
        response = self.admin_client.post(
            url,
            {"ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_delete_non_admin_gets_403(self):
        url = reverse("bulk-case-delete")
        response = self.client.post(
            url,
            {"ids": [str(self.past_case.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class CaseExportHistoryViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="password"
        )
        self.client.force_authenticate(user=self.user)
        self.case = Case.objects.create(
            case_reference="250099", data_subject_name="Jane Roe"
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _make_export(self, sequence, label):
        export = Export(case=self.case, sequence=sequence, label=label)
        export.export_file.save(
            f"disclosure_{sequence}.zip",
            SimpleUploadedFile(f"disclosure_{sequence}.zip", b"zip"),
            save=False,
        )
        export.save()
        return export

    def test_history_returns_exports_ordered_by_sequence(self):
        self._make_export(2, "Disclosure 2")
        self._make_export(1, "Original disclosure")

        url = reverse("case-exports", kwargs={"case_id": self.case.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual([e["sequence"] for e in response.data], [1, 2])
        self.assertEqual(
            [e["label"] for e in response.data],
            ["Original disclosure", "Disclosure 2"],
        )
        self.assertIsNone(response.data[0]["created_by"])
        self.assertTrue(response.data[0]["export_file"])

    def test_history_empty_when_no_exports(self):
        url = reverse("case-exports", kwargs={"case_id": self.case.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_history_requires_authentication(self):
        anon = APIClient()
        url = reverse("case-exports", kwargs={"case_id": self.case.id})
        response = anon.get(url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_history_unknown_case_returns_404(self):
        url = reverse("case-exports", kwargs={"case_id": uuid.uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_history_surfaces_producing_review_outcome(self):
        review = InternalReview.objects.create(
            case=self.case,
            opened_by=self.user,
            status=InternalReview.Status.COMPLETED,
            outcome="DS challenge accepted",
        )
        self._make_export(1, "Original disclosure")
        second = self._make_export(2, "Disclosure 2")
        second.review = review
        second.save(update_fields=["review"])

        url = reverse("case-exports", kwargs={"case_id": self.case.id})
        response = self.client.get(url)

        self.assertIsNone(response.data[0]["review_detail"])
        self.assertEqual(
            response.data[1]["review_detail"]["outcome"],
            "DS challenge accepted",
        )
        self.assertEqual(
            response.data[1]["review_detail"]["status"], "COMPLETED"
        )


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class CaseExportDiffViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="password"
        )
        self.client.force_authenticate(user=self.user)
        self.case = Case.objects.create(
            case_reference="250066", data_subject_name="Ex Port"
        )
        self.document = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("d.txt", b"content"),
            filename="d.txt",
            file_type=".txt",
            status=Document.Status.COMPLETED,
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _make_redaction(self, **overrides):
        defaults = {
            "document": self.document,
            "start_char": 0,
            "end_char": 5,
            "text": "Alice",
            "redaction_type": Redaction.RedactionType.THIRD_PARTY_PII,
            "is_accepted": True,
            "decided_by": Redaction.DecidedBy.HUMAN,
        }
        defaults.update(overrides)
        return Redaction.objects.create(**defaults)

    def _disclose(self, sequence, label):
        from ..snapshots import snapshot_redactions

        export = Export(case=self.case, sequence=sequence, label=label)
        export.export_file.save(
            f"d{sequence}.zip",
            SimpleUploadedFile(f"d{sequence}.zip", b"zip"),
            save=False,
        )
        export.save()
        snapshot = snapshot_redactions(self.case)
        snapshot.export = export
        snapshot.save(update_fields=["export"])
        return export

    def test_first_disclosure_returns_baseline(self):
        self._make_redaction()
        export = self._disclose(1, "Original disclosure")

        url = reverse(
            "case-export-diff",
            kwargs={"case_id": self.case.id, "export_id": export.id},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["baseline"])
        self.assertIsNone(response.data["base"])

    def test_diff_reports_changes_between_disclosures(self):
        self._make_redaction()
        self._disclose(1, "Original disclosure")
        self._make_redaction(
            text="Bob",
            start_char=10,
            end_char=13,
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
        )
        second = self._disclose(2, "Disclosure 2")

        url = reverse(
            "case-export-diff",
            kwargs={"case_id": self.case.id, "export_id": second.id},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["baseline"])
        self.assertEqual(response.data["base"]["sequence"], 1)
        self.assertEqual(response.data["counts"]["added"], 1)
        self.assertEqual(response.data["added"][0]["text"], "Bob")

    def test_export_without_snapshot_returns_404(self):
        export = Export(case=self.case, sequence=1, label="Legacy")
        export.export_file.save(
            "legacy.zip",
            SimpleUploadedFile("legacy.zip", b"zip"),
            save=False,
        )
        export.save()

        url = reverse(
            "case-export-diff",
            kwargs={"case_id": self.case.id, "export_id": export.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_export_returns_404(self):
        url = reverse(
            "case-export-diff",
            kwargs={"case_id": self.case.id, "export_id": uuid.uuid4()},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_requires_authentication(self):
        export = self._disclose(1, "Original disclosure")
        anon = APIClient()
        url = reverse(
            "case-export-diff",
            kwargs={"case_id": self.case.id, "export_id": export.id},
        )
        response = anon.get(url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class CaseDisclosureDiffViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="password"
        )
        self.client.force_authenticate(user=self.user)
        self.case = Case.objects.create(
            case_reference="250077", data_subject_name="Dee Iff"
        )
        self.document = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("d.txt", b"content"),
            filename="d.txt",
            file_type=".txt",
            status=Document.Status.COMPLETED,
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _make_redaction(self):
        return Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=5,
            text="Alice",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )

    def _snapshot(self):
        from ..snapshots import snapshot_redactions

        return snapshot_redactions(self.case)

    def test_diff_returns_added_removed_modified(self):
        redaction = self._make_redaction()
        self._snapshot()
        # Modify the disclosed redaction and add a brand new one.
        Redaction.objects.filter(pk=redaction.pk).reject(
            "not needed", by=Redaction.DecidedBy.HUMAN
        )
        Redaction.objects.create(
            document=self.document,
            start_char=10,
            end_char=13,
            text="Bob",
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
            is_accepted=False,
        )

        url = reverse("case-diff", kwargs={"case_id": self.case.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["counts"]["added"], 1)
        self.assertEqual(response.data["counts"]["modified"], 1)
        self.assertEqual(response.data["counts"]["removed"], 0)
        self.assertEqual(response.data["added"][0]["text"], "Bob")
        self.assertIn("is_accepted", response.data["modified"][0]["changes"])

    def test_diff_without_disclosure_returns_404(self):
        self._make_redaction()
        url = reverse("case-diff", kwargs={"case_id": self.case.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_diff_unknown_case_returns_404(self):
        url = reverse("case-diff", kwargs={"case_id": uuid.uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_diff_requires_authentication(self):
        self._snapshot()
        anon = APIClient()
        url = reverse("case-diff", kwargs={"case_id": self.case.id})
        response = anon.get(url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class CaseReviewViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="reviewer", password="password"
        )
        self.client.force_authenticate(user=self.user)
        self.case = Case.objects.create(
            case_reference="250088", data_subject_name="Rev Iewer"
        )
        self.document = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("r.txt", b"content"),
            status=Document.Status.COMPLETED,
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _disclose(self):
        export = Export(
            case=self.case, sequence=1, label="Original disclosure"
        )
        export.export_file.save(
            "d.zip", SimpleUploadedFile("d.zip", b"zip"), save=False
        )
        export.save()
        return export

    def test_open_review_on_disclosed_case(self):
        self._disclose()
        url = reverse("case-review-open", kwargs={"case_id": self.case.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "OPEN")
        self.assertEqual(response.data["opened_by"], "reviewer")
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.Status.UNDER_REVIEW)

    def test_open_review_undisclosed_case_returns_400(self):
        url = reverse("case-review-open", kwargs={"case_id": self.case.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(self.case.reviews.exists())

    def test_open_review_is_idempotent(self):
        self._disclose()
        url = reverse("case-review-open", kwargs={"case_id": self.case.id})
        first = self.client.post(url)
        second = self.client.post(url)

        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(self.case.reviews.count(), 1)

    def test_open_review_requires_authentication(self):
        self._disclose()
        anon = APIClient()
        url = reverse("case-review-open", kwargs={"case_id": self.case.id})
        response = anon.post(url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_open_review_unknown_case_returns_404(self):
        url = reverse("case-review-open", kwargs={"case_id": uuid.uuid4()})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_case_detail_exposes_review_state(self):
        self._disclose()
        url = reverse("case-detail", kwargs={"case_id": self.case.id})

        before = self.client.get(url)
        self.assertTrue(before.data["is_disclosed"])
        self.assertIsNone(before.data["active_review"])

        self.client.post(
            reverse("case-review-open", kwargs={"case_id": self.case.id})
        )
        after = self.client.get(url)
        self.assertEqual(after.data["active_review"]["status"], "OPEN")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class CaseReviewCloseViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="closer", password="password"
        )
        self.client.force_authenticate(user=self.user)
        self.case = Case.objects.create(
            case_reference="250090", data_subject_name="Clo Ser"
        )
        self.document = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("c.txt", b"content"),
            status=Document.Status.COMPLETED,
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _disclose_and_open(self):
        export = Export(
            case=self.case, sequence=1, label="Original disclosure"
        )
        export.export_file.save(
            "d.zip", SimpleUploadedFile("d.zip", b"zip"), save=False
        )
        export.save()
        return self.client.post(
            reverse("case-review-open", kwargs={"case_id": self.case.id})
        )

    @patch("cases.models.async_task", return_value="task-id")
    def test_complete_closes_review_and_returns_completed(self, _mock_async):
        self._disclose_and_open()
        url = reverse("case-review-complete", kwargs={"case_id": self.case.id})

        response = self.client.post(url, {"outcome": "Amended"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "COMPLETED")
        self.assertEqual(response.data["outcome"], "Amended")
        self.assertEqual(response.data["closed_by"], "closer")

    def test_abandon_closes_review_and_returns_abandoned(self):
        self._disclose_and_open()
        url = reverse("case-review-abandon", kwargs={"case_id": self.case.id})

        response = self.client.post(
            url, {"outcome": "Withdrawn"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ABANDONED")

    def test_close_without_outcome_returns_400(self):
        self._disclose_and_open()
        url = reverse("case-review-abandon", kwargs={"case_id": self.case.id})

        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_close_without_open_review_returns_404(self):
        # Disclosed but no review opened.
        export = Export(
            case=self.case, sequence=1, label="Original disclosure"
        )
        export.export_file.save(
            "d.zip", SimpleUploadedFile("d.zip", b"zip"), save=False
        )
        export.save()
        url = reverse("case-review-complete", kwargs={"case_id": self.case.id})

        response = self.client.post(url, {"outcome": "x"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_close_requires_authentication(self):
        self._disclose_and_open()
        anon = APIClient()
        url = reverse("case-review-abandon", kwargs={"case_id": self.case.id})

        response = anon.post(url, {"outcome": "x"}, format="json")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RedactionPropagationViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="prop", password="password"
        )
        self.client.force_authenticate(user=self.user)
        self.case = Case.objects.create(
            case_reference="250099", data_subject_name="Prop Agate"
        )
        self.source_doc = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("s.txt", b"content"),
            status=Document.Status.COMPLETED,
            extracted_text="Alice met Bob.",
        )
        self.other_doc = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("o.txt", b"content"),
            status=Document.Status.COMPLETED,
            extracted_text="Alice was mentioned here too.",
        )
        # Disclose + open a review so marking DS_INFO does not auto-propagate.
        export = Export(case=self.case, sequence=1, label="Original")
        export.export_file.save(
            "d.zip", SimpleUploadedFile("d.zip", b"zip"), save=False
        )
        export.save()
        InternalReview.objects.create(
            case=self.case, status=InternalReview.Status.OPEN
        )
        self.source = Redaction.objects.create(
            document=self.source_doc,
            start_char=0,
            end_char=5,
            text="Alice",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _url(self, redaction_id=None):
        return reverse(
            "redaction-propagation",
            kwargs={"redaction_id": redaction_id or self.source.id},
        )

    def test_preview_lists_affected_documents_without_applying(self):
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["term"], "Alice")
        self.assertEqual(response.data["total_matches"], 1)
        docs = response.data["affected_documents"]
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["document_id"], str(self.other_doc.id))
        self.assertEqual(docs[0]["match_count"], 1)
        # Preview is read-only — nothing was written.
        self.assertFalse(self.other_doc.redactions.exists())

    def test_apply_propagates_across_the_case(self):
        response = self.client.post(self._url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_matches"], 1)
        propagated = self.other_doc.redactions.get(text="Alice")
        self.assertEqual(
            propagated.redaction_type,
            Redaction.RedactionType.DS_INFORMATION,
        )
        self.assertTrue(propagated.is_accepted)

    def test_apply_is_a_system_write_exempt_from_the_lock(self):
        # Re-lock the case by closing the review. A human decision write would
        # now be rejected, but propagation applies as a DS_PROP system write.
        self.case.reviews.update(status=InternalReview.Status.COMPLETED)

        response = self.client.post(self._url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            self.other_doc.redactions.filter(
                text="Alice", is_accepted=True
            ).exists()
        )

    def test_preview_on_non_ds_info_redaction_returns_400(self):
        other = Redaction.objects.create(
            document=self.source_doc,
            start_char=9,
            end_char=12,
            text="Bob",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        response = self.client.get(self._url(other.id))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_on_non_ds_info_redaction_returns_400(self):
        other = Redaction.objects.create(
            document=self.source_doc,
            start_char=9,
            end_char=12,
            text="Bob",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        response = self.client.post(self._url(other.id))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(self.other_doc.redactions.exists())

    def test_unknown_redaction_returns_404(self):
        response = self.client.get(self._url(uuid.uuid4()))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_requires_authentication(self):
        anon = APIClient()
        response = anon.get(self._url())

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
