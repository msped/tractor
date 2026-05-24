import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from cases.models import Case, Document, Redaction
from training.tests.base import NetworkBlockerMixin

MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RedactionSignalTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="SIG001",
            data_subject_name="Jane Signal",
        )
        self.document = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("sig.txt", b"content"),
            status=Document.Status.READY_FOR_REVIEW,
            extracted_text="Jane Signal was here.",
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    @patch("django_q.tasks.async_task")
    def test_creating_ds_info_redaction_triggers_task(self, mock_async_task):
        Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="Jane",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
        )
        mock_async_task.assert_called_once()
        args = mock_async_task.call_args[0]
        self.assertEqual(
            args[0], "cases.tasks.find_and_flag_matching_text_in_case"
        )

    @patch("django_q.tasks.async_task")
    def test_creating_non_ds_info_redaction_does_not_trigger_task(
        self, mock_async_task
    ):
        Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="Jane",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        mock_async_task.assert_not_called()

    @patch("django_q.tasks.async_task")
    def test_updating_redaction_type_to_ds_info_triggers_task(
        self, mock_async_task
    ):
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="Jane",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        mock_async_task.reset_mock()

        redaction.redaction_type = Redaction.RedactionType.DS_INFORMATION
        redaction.save()

        mock_async_task.assert_called_once()
        args = mock_async_task.call_args[0]
        self.assertEqual(
            args[0], "cases.tasks.find_and_flag_matching_text_in_case"
        )

    @patch("django_q.tasks.async_task")
    def test_saving_existing_ds_info_without_type_change_does_not_trigger_task(
        self, mock_async_task
    ):
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="Jane",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
        )
        mock_async_task.reset_mock()

        # Accept without changing type — should not re-trigger
        redaction.is_accepted = True
        redaction.save()

        mock_async_task.assert_not_called()

    @patch("django_q.tasks.async_task")
    def test_updating_type_to_ds_info_without_update_fields_triggers_task(
        self, mock_async_task
    ):
        """DRF saves without update_fields; the signal must still fire."""
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="Jane",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        mock_async_task.reset_mock()

        # Simulate DRF's serializer.save() — no update_fields kwarg
        redaction.redaction_type = Redaction.RedactionType.DS_INFORMATION
        redaction.is_accepted = True
        redaction.is_suggestion = False
        redaction.save()  # no update_fields

        mock_async_task.assert_called_once()
