import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from cases.models import Case, Document, Export, InternalReview, Redaction
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

    def _create_ds_info(self, **kwargs):
        """A DS_INFO redaction, human-accepted unless told otherwise."""
        fields = {
            "is_accepted": True,
            "decided_by": Redaction.DecidedBy.HUMAN,
            **kwargs,
        }
        return Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="Jane",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
            **fields,
        )

    @patch("django_q.tasks.async_task")
    def test_human_accepting_ds_info_on_creation_triggers_task(
        self, mock_async_task
    ):
        """A manual highlight marked DS_INFO — accepted as it is created."""
        self._create_ds_info()

        mock_async_task.assert_called_once()
        args = mock_async_task.call_args[0]
        self.assertEqual(
            args[0], "cases.tasks.find_and_flag_matching_text_in_case"
        )

    @patch("django_q.tasks.async_task")
    def test_pending_ds_info_suggestion_does_not_trigger_task(
        self, mock_async_task
    ):
        """
        Span resolution proposes DS_INFO it has inferred, pending a reviewer's
        confirmation. Propagating it case-wide before anyone has confirmed it
        would spread an unconfirmed inference.
        """
        self._create_ds_info(is_accepted=False, decided_by=None)

        mock_async_task.assert_not_called()

    @patch("django_q.tasks.async_task")
    def test_system_accepted_ds_info_does_not_trigger_task(
        self, mock_async_task
    ):
        """
        A record match is the system recognising the case's own entry, not a
        human decision — so it is not a human decision spreading. Each
        document's own resolution pass covers it.
        """
        self._create_ds_info(decided_by=Redaction.DecidedBy.DS_RECORD_MATCH)

        mock_async_task.assert_not_called()

    @patch("django_q.tasks.async_task")
    def test_human_confirming_a_pending_suggestion_triggers_task(
        self, mock_async_task
    ):
        """
        The reviewer confirms an inference the system proposed. The type does
        not change — only the decision — so a type-change trigger would miss
        it entirely and nothing would ever spread.
        """
        redaction = self._create_ds_info(is_accepted=False, decided_by=None)
        mock_async_task.reset_mock()

        redaction.is_accepted = True
        redaction.decided_by = Redaction.DecidedBy.HUMAN
        redaction.save()

        mock_async_task.assert_called_once()

    @patch("django_q.tasks.async_task")
    def test_human_rejecting_ds_info_does_not_trigger_task(
        self, mock_async_task
    ):
        """A decision *not* to treat the text as the data subject's."""
        redaction = self._create_ds_info(is_accepted=False, decided_by=None)
        mock_async_task.reset_mock()

        redaction.decided_by = Redaction.DecidedBy.HUMAN
        redaction.justification = "A different person"
        redaction.save()

        mock_async_task.assert_not_called()

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
    def test_changing_type_to_ds_info_and_accepting_triggers_task(
        self, mock_async_task
    ):
        """
        Change-type-and-accept: the frontend sends redaction_type together
        with is_accepted=true (useRedactionActions.handleChangeTypeAndAccept).
        """
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="Jane",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        mock_async_task.reset_mock()

        redaction.redaction_type = Redaction.RedactionType.DS_INFORMATION
        redaction.is_accepted = True
        redaction.decided_by = Redaction.DecidedBy.HUMAN
        redaction.save()

        mock_async_task.assert_called_once()
        args = mock_async_task.call_args[0]
        self.assertEqual(
            args[0], "cases.tasks.find_and_flag_matching_text_in_case"
        )

    @patch("django_q.tasks.async_task")
    def test_changing_type_to_ds_info_without_accepting_does_not_trigger(
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

        mock_async_task.assert_not_called()

    @patch("django_q.tasks.async_task")
    def test_resaving_an_already_accepted_ds_info_does_not_retrigger(
        self, mock_async_task
    ):
        """The acceptance already propagated when it landed."""
        redaction = self._create_ds_info()
        mock_async_task.reset_mock()

        redaction.text = "Jane S"
        redaction.save()

        mock_async_task.assert_not_called()

    @patch("django_q.tasks.async_task")
    def test_open_review_suppresses_the_propagation_task(
        self, mock_async_task
    ):
        """During a review, propagation is driven by the reviewer's
        preview/confirm — the automatic task must not fire."""
        Export.objects.create(
            case=self.case,
            export_file=SimpleUploadedFile("d.zip", b"zip"),
            sequence=1,
        )
        InternalReview.objects.create(
            case=self.case, status=InternalReview.Status.OPEN
        )

        self._create_ds_info()

        mock_async_task.assert_not_called()

    @patch("django_q.tasks.async_task")
    def test_closed_review_does_not_suppress_the_propagation_task(
        self, mock_async_task
    ):
        InternalReview.objects.create(
            case=self.case, status=InternalReview.Status.COMPLETED
        )

        self._create_ds_info()

        mock_async_task.assert_called_once()

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
        redaction.decided_by = Redaction.DecidedBy.HUMAN
        redaction.is_suggestion = False
        redaction.save()  # no update_fields

        mock_async_task.assert_called_once()
