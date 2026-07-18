import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from training.tests.base import NetworkBlockerMixin

from ..models import Case, Document, Export, InternalReview
from ..reviews import ReviewError, open_review

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
