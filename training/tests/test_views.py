import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django_q.models import Schedule
from rest_framework import status
from rest_framework.test import APITestCase, override_settings, APIClient

from ..models import Model, TrainingDocument

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(
    MEDIA_ROOT=MEDIA_ROOT, Q_CLUSTER={"sync": True}
)
class BaseTrainingAPITestCase(APITestCase):
    """Base class for training API tests with shared setup."""

    def setUp(self):
        """Set up users and initial data for tests."""
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        self.regular_user = User.objects.create_user(
            "user", "user@example.com", "password"
        )

        self.model = Model.objects.create(
            name="test_model_v1", path="/path/to/model_v1"
        )
        self.docx_file = SimpleUploadedFile(
            "test.docx",
            b"file_content",
            "application/vnd.openxmlformats-officedocument\
                wordprocessingml.document",
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)


class ModelViewTests(BaseTrainingAPITestCase):
    def test_unauthenticated_access_to_model_views_fails(self):
        """Unauthenticated users get 401 on model views."""
        list_url = reverse("model-list-create")
        detail_url = reverse("model-detail",
                             kwargs={"pk": self.model.pk})
        set_active_url = reverse(
            "model-set-active", kwargs={"pk": self.model.pk}
        )

        self.assertEqual(self.client.get(list_url).status_code,
                         status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(detail_url).status_code,
                         status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.post(
            set_active_url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_access_to_model_views_fails(self):
        """Non-admin users get 403 on model views."""
        self.client.force_authenticate(user=self.regular_user)
        list_url = reverse("model-list-create")
        detail_url = reverse("model-detail",
                             kwargs={"pk": self.model.pk})
        set_active_url = reverse(
            "model-set-active", kwargs={"pk": self.model.pk}
        )

        self.assertEqual(self.client.get(list_url).status_code,
                         status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(
            detail_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post(
            set_active_url).status_code, status.HTTP_403_FORBIDDEN)

    def test_list_models_as_admin(self):
        """Admin can list all models. Should be 2 (1 from setup, 1 new)."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("model-list-create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["name"], self.model.name)

    def test_create_model_as_admin(self):
        """Admin can create a new model entry."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("model-list-create")
        data = {"name": "new-model-v2"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Model.objects.count(), 3)

    def test_delete_model_as_admin(self):
        """Admin can delete a model entry. Should leave 1 model (default)"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("model-detail", kwargs={"pk": self.model.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Model.objects.count(), 1)

    @patch("training.views.SpacyModelManager")
    def test_set_active_model_as_admin(self, mock_model_manager):
        """Admin can set a model to active."""
        mock_manager_instance = mock_model_manager.get_instance.return_value
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("model-set-active",
                      kwargs={"pk": self.model.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_model_manager.get_instance.assert_called_once()
        mock_manager_instance.switch_model.assert_called_once_with(
            self.model.name
        )

    def test_set_active_model_not_found(self):
        """Setting a non-existent model as active returns 404."""
        self.client.force_authenticate(user=self.admin_user)
        non_existent_pk = "11111111-1111-1111-1111-111111111111"
        url = reverse("model-set-active",
                      kwargs={"pk": non_existent_pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TrainingDocumentViewTests(BaseTrainingAPITestCase):
    def test_unauthenticated_access_fails(self):
        """Unauthenticated users get 401."""
        url = reverse("training-document-list")
        self.assertEqual(self.client.get(url).status_code,
                         status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_access_fails(self):
        """Non-admin users get 403."""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse("training-document-list")
        self.assertEqual(self.client.get(url).status_code,
                         status.HTTP_403_FORBIDDEN)

    def test_create_training_doc_as_admin(self):
        """Admin can upload a .docx training document."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("training-document-list")
        data = {"name": "test.docx", "original_file": self.docx_file}
        response = self.client.post(url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TrainingDocument.objects.count(), 1)
        doc = TrainingDocument.objects.first()
        self.assertEqual(doc.created_by, self.admin_user)
        self.assertTrue(doc.original_file.name.endswith("test.docx"))

    def test_create_training_doc_wrong_file_type(self):
        """Uploading a non-docx file should fail with a 400 error."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("training-document-list")
        txt_file = SimpleUploadedFile("test.txt", b"file_content")
        data = {"name": "test.txt", "original_file": txt_file}
        response = self.client.post(url, data, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Only .docx files are supported.",
                      str(response.data))
        self.assertEqual(TrainingDocument.objects.count(), 0)


class TrainingScheduleViewTests(BaseTrainingAPITestCase):
    def test_unauthenticated_access_fails(self):
        """Unauthenticated users get 401."""
        url = reverse("schedule-list")
        self.assertEqual(self.client.get(url).status_code,
                         status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_access_fails(self):
        """Non-admin users get 403."""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse("schedule-list")
        self.assertEqual(self.client.get(url).status_code,
                         status.HTTP_403_FORBIDDEN)

    def test_list_schedules_as_admin(self):
        """Admin can list training schedules."""
        Schedule.objects.create(
            func="training.tasks.train_model", schedule_type=Schedule.DAILY
        )
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("schedule-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["func"],
                         "training.tasks.train_model")

    def test_create_schedule_as_admin(self):
        """Admin can create a new training schedule."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("schedule-list")
        data = {
            "func": "training.tasks.train_model",
            "schedule_type": Schedule.WEEKLY,
            "kwargs": "redactions",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Schedule.objects.filter(
            func="training.tasks.train_model").exists())


class RunManualTrainingViewTests(BaseTrainingAPITestCase):
    def test_unauthenticated_access_fails(self):
        """Unauthenticated users get 401."""
        url = reverse("training-run-now")
        self.assertEqual(self.client.post(url).status_code,
                         status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_cannot_trigger_training(self):
        """Any authenticated user can trigger manual training."""
        TrainingDocument.objects.create(
            name="doc1",
            original_file=self.docx_file,
            created_by=self.regular_user
        )
        self.client.force_authenticate(user=self.regular_user)
        url = reverse("training-run-now")
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("training.views.async_task")
    def test_run_manual_training_triggers_task(self, mock_async_task):
        """POST to run-now triggers the async_task."""
        TrainingDocument.objects.create(
            name="doc1",
            original_file=self.docx_file,
            created_by=self.admin_user
        )
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("training-run-now")
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["status"], "training started")
        self.assertEqual(response.data["documents"], 1)
        mock_async_task.assert_called_once_with(
            "training.tasks.train_model",
            source="training_docs",
            user=self.admin_user
        )

    def test_run_manual_training_no_docs(self):
        """POST to run-now returns 400 if no unprocessed docs exist."""
        TrainingDocument.objects.all().delete()
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("training-run-now")
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"],
                         "No unprocessed training documents found.")


class TrainingRunViewTests(BaseTrainingAPITestCase):
    def test_unauthenticated_access_fails(self):
        """Unauthenticated users get 401."""
        url = reverse("training-run-list")
        self.assertEqual(self.client.get(url).status_code,
                         status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_access_fails(self):
        """Non-admin users get 403."""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse("training-run-list")
        self.assertEqual(self.client.get(url).status_code,
                         status.HTTP_403_FORBIDDEN)

    def test_list_training_runs_as_admin(self):
        """Admin can list all training runs."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("training-run-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
