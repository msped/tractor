import os
import shutil
import tempfile
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import date
from freezegun import freeze_time
from dateutil.relativedelta import relativedelta
from cases.models import Case, Document, Redaction, RedactionContext
from training.models import Model
from training.tests.base import NetworkBlockerMixin

User = get_user_model()

MEDIA_ROOT = tempfile.mkdtemp()


def return_test_file_name(filename):
    return os.path.basename(filename)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class CaseModelTests(NetworkBlockerMixin, TestCase):
    def test_case_str(self):
        case = Case.objects.create(
            case_reference="202501",
            data_subject_name="Alice Example"
        )
        self.assertIn("Case 202501 - Alice Example", str(case))

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_case_creation_with_user(self):
        user = User.objects.create_user(
            username='testuser', password='password')
        case = Case.objects.create(
            case_reference="20251A",
            data_subject_name="User Test",
            created_by=user
        )
        self.assertEqual(case.created_by, user)
        self.assertEqual(case.created_by.username, 'testuser')

    @freeze_time("2025-09-27")
    def test_retention_review_date_for_adult(self):
        # Test that the save() method correctly sets the date on creation
        dob = date(2005, 9, 27)  # 20 years old
        case = Case.objects.create(
            case_reference="202502",
            data_subject_name="Adult Example",
            data_subject_dob=dob
        )
        expected = date(2031, 9, 27)  # 2025 + 6 years
        self.assertEqual(case.retention_review_date, expected)

    def test_calculate_retention_date_for_adult_direct(self):
        fixed_today = date(2025, 9, 27)
        dob = fixed_today - relativedelta(years=25)
        case = Case(
            case_reference="20252A",
            data_subject_name="Adult Direct",
            data_subject_dob=dob
        )
        case.retention_review_date = case._calculate_retention_date(
            today=fixed_today)
        expected = fixed_today + relativedelta(years=6)
        self.assertEqual(case.retention_review_date, expected)

    def test_retention_review_date_for_minor(self):
        fixed_today = date(2024, 9, 27)
        dob = date(2015, 9, 27)
        case = Case(
            case_reference="202503",
            data_subject_name="Minor Example",
            data_subject_dob=dob
        )
        # With today as 2024-09-27, the subject is 9.
        # The rule for minors applies.
        # 18th birthday is 2033-09-27. Retention is 6 years after: 2039-09-27.
        calculated_date = case._calculate_retention_date(today=fixed_today)
        self.assertEqual(calculated_date, date(2039, 9, 27))

    def test_retention_review_date_for_eighteen_year_old(self):
        # Test edge case: someone who is exactly 18
        fixed_today = date(2025, 9, 27)
        dob = fixed_today - relativedelta(years=18)  # DOB is 2007-09-27
        case = Case(
            case_reference="20253B",
            data_subject_name="18yo",
            data_subject_dob=dob
        )
        # For someone who is exactly 18, the rule is still 6 years from today.
        calculated_date = case._calculate_retention_date(today=fixed_today)
        self.assertEqual(calculated_date, fixed_today + relativedelta(years=6))

    @freeze_time("2025-09-27")
    def test_retention_review_date_no_dob(self):
        # Test that save() correctly sets the date when DOB is not provided
        case = Case.objects.create(
            case_reference="202504",
            data_subject_name="No DOB"
        )
        expected = date(2031, 9, 27)  # 2025 + 6 years
        self.assertEqual(case.retention_review_date, expected)

    def test_case_status_default(self):
        case = Case.objects.create(
            case_reference="202505",
            data_subject_name="Status Default"
        )
        self.assertEqual(case.status, Case.Status.OPEN)

    def test_case_export_status_default(self):
        case = Case.objects.create(
            case_reference="202506",
            data_subject_name="Export Status Default"
        )
        self.assertEqual(case.export_status, Case.ExportStatus.NONE)

    @patch("cases.models.async_task")
    def test_start_export_method(self, mock_async_task):
        """Test the start_export method on the Case model."""
        mock_async_task.return_value = "model-test-task-id"
        case = Case.objects.create(
            case_reference="202507",
            data_subject_name="Export Method Test"
        )
        self.assertEqual(case.export_status, Case.ExportStatus.NONE)

        task_id = case.start_export()

        self.assertEqual(task_id, "model-test-task-id")
        mock_async_task.assert_called_once_with(
            "cases.services.export_case_documents", case.id)
        self.assertEqual(case.export_status, Case.ExportStatus.PROCESSING)
        self.assertEqual(case.export_task_id, "model-test-task-id")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class DocumentModelTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="202510",
            data_subject_name="Doc Test"
        )
        self.model = Model.objects.create(
            name="Test Model"
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_document_str(self):
        file = SimpleUploadedFile("test.pdf", b"file_content")
        doc = Document.objects.create(
            case=self.case,
            original_file=file,
            spacy_model=self.model
        )
        self.assertEqual("test.pdf", return_test_file_name(
            doc.original_file.name))

    def test_document_filename_and_filetype(self):
        file = SimpleUploadedFile("sample.docx", b"file_content")
        doc = Document.objects.create(
            case=self.case,
            original_file=file
        )
        self.assertEqual(return_test_file_name(
            doc.original_file.name), "sample.docx")
        self.assertIn(".docx", doc.original_file.name)

    def test_document_filename_and_filetype_on_save(self):
        file = SimpleUploadedFile("report.pdf", b"file_content")
        doc = Document.objects.create(
            case=self.case,
            original_file=file
        )
        self.assertEqual(return_test_file_name(
            doc.original_file.name), "report.pdf")
        self.assertIn(".pdf", return_test_file_name(
            doc.original_file.name
        ))

    def test_document_status_default(self):
        file = SimpleUploadedFile("default.txt", b"file_content")
        doc = Document.objects.create(
            case=self.case,
            original_file=file
        )
        self.assertEqual(doc.status, Document.Status.PROCESSING)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RedactionModelTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="202520",
            data_subject_name="Redaction Test"
        )
        file = SimpleUploadedFile("redact.txt", b"file_content")
        self.document = Document.objects.create(
            case=self.case,
            original_file=file
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_redaction_str(self):
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=10,
            text="Sensitive Data",
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA
        )
        self.assertIn("Sensitive Data", str(redaction))

    def test_redaction_with_justification(self):
        justification_text = "This is a manual redaction for a specific " \
            "reason."
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=10,
            text="Secret Info",
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
            is_suggestion=False,
            is_accepted=True,
            justification=justification_text
        )
        self.assertEqual(redaction.justification, justification_text)

    def test_redaction_defaults(self):
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=5,
            end_char=15,
            text="PII Example",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII
        )
        self.assertTrue(redaction.is_suggestion)
        self.assertFalse(redaction.is_accepted)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RedactionContextModelTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="202530",
            data_subject_name="Context Test"
        )
        file = SimpleUploadedFile("context.txt", b"file_content")
        self.document = Document.objects.create(
            case=self.case,
            original_file=file
        )
        self.redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="test"
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_redaction_context_creation_and_str(self):
        """Test creating a RedactionContext and its string representation."""
        context = RedactionContext.objects.create(
            redaction=self.redaction, text="This is context."
        )
        self.assertEqual(RedactionContext.objects.count(), 1)
        self.assertEqual(context.redaction, self.redaction)
        self.assertEqual(context.text, "This is context.")
