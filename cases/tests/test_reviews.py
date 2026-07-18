import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from training.tests.base import NetworkBlockerMixin

from ..models import Case, Document, Export, InternalReview, Redaction
from ..reviews import (
    ReviewError,
    abandon_review,
    complete_review,
    open_review,
)
from ..snapshots import snapshot_redactions

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class OpenReviewTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reviewer", password="password"
        )
        self.case = Case.objects.create(
            case_reference="202570", data_subject_name="Review Test"
        )
        self.document = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("r.txt", b"content"),
            status=Document.Status.COMPLETED,
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _disclose(self, sequence=1):
        return Export.objects.create(
            case=self.case,
            export_file=SimpleUploadedFile("d.zip", b"zip"),
            sequence=sequence,
            label="Original disclosure",
        )

    def test_open_requires_a_disclosed_case(self):
        with self.assertRaises(ReviewError):
            open_review(self.case, by=self.user)
        self.assertFalse(self.case.reviews.exists())

    def test_open_creates_review_and_moves_case_under_review(self):
        self._disclose()

        review = open_review(self.case, by=self.user)

        self.assertEqual(review.status, InternalReview.Status.OPEN)
        self.assertEqual(review.opened_by, self.user)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.Status.UNDER_REVIEW)

    def test_open_leaves_documents_completed_and_editable(self):
        self._disclose()

        open_review(self.case, by=self.user)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.COMPLETED)

    def test_open_is_idempotent_returns_existing_open_review(self):
        self._disclose()

        first = open_review(self.case, by=self.user)
        second = open_review(self.case, by=self.user)

        self.assertEqual(first.id, second.id)
        self.assertEqual(
            self.case.reviews.filter(
                status=InternalReview.Status.OPEN
            ).count(),
            1,
        )

    def test_open_after_closed_review_starts_a_new_one(self):
        self._disclose()
        InternalReview.objects.create(
            case=self.case, status=InternalReview.Status.COMPLETED
        )

        review = open_review(self.case, by=self.user)

        self.assertEqual(review.status, InternalReview.Status.OPEN)
        self.assertEqual(self.case.reviews.count(), 2)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class CloseReviewTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="closer", password="password"
        )
        self.case = Case.objects.create(
            case_reference="202571", data_subject_name="Close Test"
        )
        self.document = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("c.txt", b"content"),
            status=Document.Status.COMPLETED,
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _disclose(self, snapshot=True):
        """Preserve an as-disclosed Export, optionally with a linked snapshot."""
        export = Export.objects.create(
            case=self.case,
            export_file=SimpleUploadedFile("d.zip", b"zip"),
            sequence=self.case.exports.count() + 1,
            label="Original disclosure",
        )
        if snapshot:
            snap = snapshot_redactions(self.case)
            snap.export = export
            snap.save(update_fields=["export"])
        return export

    def _open(self):
        return open_review(self.case, by=self.user)

    # ---- complete ----
    @patch("cases.models.async_task")
    def test_complete_requires_a_written_outcome(self, mock_async_task):
        self._disclose()
        review = self._open()

        with self.assertRaises(ReviewError):
            complete_review(review, outcome="   ", by=self.user)

        review.refresh_from_db()
        self.assertEqual(review.status, InternalReview.Status.OPEN)
        mock_async_task.assert_not_called()

    @patch("cases.models.async_task", return_value="task-xyz")
    def test_complete_closes_relocks_and_triggers_review_export(
        self, mock_async_task
    ):
        self._disclose()
        review = self._open()

        completed = complete_review(
            review, outcome="Amended after DS challenge", by=self.user
        )

        self.assertEqual(completed.status, InternalReview.Status.COMPLETED)
        self.assertEqual(completed.outcome, "Amended after DS challenge")
        self.assertEqual(completed.closed_by, self.user)
        self.assertIsNotNone(completed.closed_at)

        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.Status.COMPLETED)
        # The re-export is attributed to this review.
        mock_async_task.assert_called_once_with(
            "cases.tasks.export_case_documents",
            self.case.id,
            str(review.id),
        )

    @patch("cases.models.async_task", return_value="task-id")
    def test_complete_rejects_an_already_closed_review(self, mock_async_task):
        self._disclose()
        review = self._open()
        complete_review(review, outcome="First close", by=self.user)
        mock_async_task.reset_mock()

        with self.assertRaises(ReviewError):
            complete_review(review, outcome="Second close", by=self.user)

        mock_async_task.assert_not_called()

    # ---- abandon ----
    @patch("cases.models.async_task")
    def test_abandon_requires_a_written_outcome(self, mock_async_task):
        self._disclose()
        review = self._open()

        with self.assertRaises(ReviewError):
            abandon_review(review, outcome="", by=self.user)

        review.refresh_from_db()
        self.assertEqual(review.status, InternalReview.Status.OPEN)

    def test_abandon_restores_redactions_from_snapshot_and_relocks(self):
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="Data",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        # Freeze the as-disclosed state (redaction still pending).
        self._disclose()
        review = self._open()

        # Edits made during the review: accept the existing redaction and add
        # a new one.
        Redaction.objects.filter(id=redaction.id).accept(
            by=Redaction.DecidedBy.HUMAN
        )
        extra = Redaction.objects.create(
            document=self.document,
            start_char=5,
            end_char=9,
            text="More",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )

        abandoned = abandon_review(
            review, outcome="Challenge withdrawn", by=self.user
        )

        self.assertEqual(abandoned.status, InternalReview.Status.ABANDONED)
        self.assertEqual(abandoned.outcome, "Challenge withdrawn")
        self.assertEqual(abandoned.closed_by, self.user)
        # Edits are rolled back: the added redaction is gone and the accept is
        # reverted to the frozen pending state.
        self.assertFalse(Redaction.objects.filter(id=extra.id).exists())
        restored = Redaction.objects.get(id=redaction.id)
        self.assertFalse(restored.is_accepted)
        self.assertIsNone(restored.decided_by)

        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.Status.COMPLETED)

    @patch("cases.models.async_task")
    def test_abandon_produces_no_export(self, mock_async_task):
        self._disclose()
        review = self._open()
        before = self.case.exports.count()

        abandon_review(review, outcome="No change needed", by=self.user)

        mock_async_task.assert_not_called()
        self.assertEqual(self.case.exports.count(), before)

    def test_abandon_without_a_snapshot_still_closes(self):
        """A legacy disclosure with no snapshot abandons without restoring."""
        self._disclose(snapshot=False)
        review = self._open()

        abandoned = abandon_review(
            review, outcome="Nothing to restore", by=self.user
        )

        self.assertEqual(abandoned.status, InternalReview.Status.ABANDONED)
