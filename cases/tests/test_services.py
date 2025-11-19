import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import date
from unittest.mock import MagicMock, patch, call

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from ..models import Case, Document, Redaction
from ..services import (
    _generate_pdf_from_document,
    export_case_documents,
    find_and_flag_matching_text_in_case,
    process_document_and_create_redactions,
)
from ..services import delete_cases_past_retention_date
from training.models import Model as SpacyModel
from training.tests.base import NetworkBlockerMixin

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ServiceTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        """Set up test data for all service tests."""
        self.user = User.objects.create_user(
            username="testuser", password="password"
        )
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
            status=Document.Status.PROCESSING,
        )
        self.spacy_model = SpacyModel.objects.create(
            name="en_test_model", is_active=True
        )

    def tearDown(self):
        """Clean up the temporary media directory."""
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    @patch("cases.services.extract_entities_from_text")
    @patch("cases.services.SpacyModelManager")
    def test_process_document_and_create_redactions_success(
        self, mock_spacy_manager, mock_extract_entities
    ):
        """Test successful processing of a document and
        creation of redactions."""
        # Mock the SpacyModelManager
        mock_manager_instance = MagicMock()
        mock_manager_instance.get_model_entry.return_value = self.spacy_model
        mock_spacy_manager.get_instance.return_value = mock_manager_instance

        # Mock the entity extraction
        extracted_text = "This text contains PII like a name."
        suggestions = [
            {"start_char": 21, "end_char": 24, "text": "PII"},
            {"start_char": 31, "end_char": 35, "text": "name"},
        ]
        mock_extract_entities.return_value = (extracted_text, suggestions)

        process_document_and_create_redactions(self.document.id)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status,
                         Document.Status.READY_FOR_REVIEW)
        self.assertEqual(self.document.extracted_text, extracted_text)
        self.assertEqual(self.document.spacy_model, self.spacy_model)
        self.assertEqual(self.document.redactions.count(), 2)

        first_redaction = self.document.redactions.first()
        self.assertEqual(first_redaction.text, "PII")
        self.assertTrue(first_redaction.is_suggestion)
        self.assertFalse(first_redaction.is_accepted)

        mock_extract_entities.assert_called_once_with(
            self.document.original_file.path)

    @patch("cases.services.SpacyModelManager")
    @patch("cases.services.extract_entities_from_text")
    def test_process_document_extraction_fails(
        self, mock_extract_entities, mock_spacy_manager
    ):
        """Test document processing when text extraction returns nothing."""
        mock_extract_entities.return_value = (None, [])
        # Mock the SpacyModelManager to prevent it from trying to load a model
        mock_manager_instance = MagicMock()
        mock_manager_instance.get_model_entry.return_value = self.spacy_model
        mock_spacy_manager.get_instance.return_value = mock_manager_instance

        process_document_and_create_redactions(self.document.id)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.ERROR)
        self.assertIsNone(self.document.extracted_text)
        self.assertEqual(self.document.redactions.count(), 0)

    def test_process_document_not_found(self):
        """Test that the function handles a non-existent document ID
        gracefully."""
        non_existent_id = uuid.uuid4()
        # This should run without raising an exception
        process_document_and_create_redactions(non_existent_id)
        self.assertFalse(Document.objects.filter(id=non_existent_id).exists())

    def test_find_and_flag_matching_text(self):
        """Test finding and creating new redactions for matching text."""
        # Setup: A second document in the same case
        doc2_text = "The subject's name is John Doe. Another name is Jane Doe."
        doc2 = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("doc2.txt", doc2_text.encode()),
            extracted_text=doc2_text,
            status=Document.Status.READY_FOR_REVIEW,
        )

        # Create the source redaction that triggers the service
        source_redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="name",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
        )

        find_and_flag_matching_text_in_case(source_redaction.id)

        # Check that new redactions were created in the second document
        doc2.refresh_from_db()
        self.assertEqual(doc2.redactions.count(), 2)

        new_redactions = doc2.redactions.all()
        self.assertEqual(new_redactions[0].text, "name")
        self.assertEqual(
            new_redactions[0].redaction_type,
            Redaction.RedactionType.DS_INFORMATION
        )
        self.assertTrue(new_redactions[0].is_suggestion)

        self.assertEqual(new_redactions[1].text, "name")
        self.assertEqual(
            new_redactions[1].redaction_type,
            Redaction.RedactionType.DS_INFORMATION
        )

    def test_find_and_flag_updates_existing_redaction(self):
        """Test that an existing redaction is updated to DS_INFO."""
        doc2_text = "This text contains a name."
        doc2 = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("doc2.txt", doc2_text.encode()),
            extracted_text=doc2_text,
            status=Document.Status.COMPLETED,
        )
        # An existing, different redaction for the word "name"
        existing_redaction = Redaction.objects.create(
            document=doc2,
            start_char=21,
            end_char=25,
            text="name",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_suggestion=False,
            is_accepted=True,
        )

        # The trigger redaction
        source_redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="name",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
        )

        find_and_flag_matching_text_in_case(source_redaction.id)

        existing_redaction.refresh_from_db()
        self.assertEqual(existing_redaction.redaction_type,
                         Redaction.RedactionType.DS_INFORMATION)
        self.assertTrue(existing_redaction.is_suggestion)
        self.assertFalse(existing_redaction.is_accepted)
        self.assertIsNone(existing_redaction.justification)

        # Check that the document status was reverted for review
        doc2.refresh_from_db()
        self.assertEqual(doc2.status, Document.Status.READY_FOR_REVIEW)

    def test_generate_pdf_from_document(self):
        """Test the internal PDF generation function."""
        self.document.extracted_text = "This is some text with PII to redact."
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=23,
            end_char=26,
            text="PII",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
        )

        # Test disclosure mode (black box)
        pdf_content_disclosure = _generate_pdf_from_document(
            self.document, mode="disclosure"
        )
        self.assertIsNotNone(pdf_content_disclosure)
        self.assertIsInstance(pdf_content_disclosure, bytes)
        # A simple check to see if the PDF content seems valid
        self.assertTrue(pdf_content_disclosure.startswith(b"%PDF-"))

        # Test redacted mode (color highlight)
        pdf_content_redacted = _generate_pdf_from_document(
            self.document, mode="redacted"
        )
        self.assertIsNotNone(pdf_content_redacted)
        self.assertIsInstance(pdf_content_redacted, bytes)
        self.assertTrue(pdf_content_redacted.startswith(b"%PDF-"))

    def test_generate_pdf_no_text(self):
        """Test PDF generation for a document with no extracted text."""
        self.document.extracted_text = ""
        self.document.save()
        pdf_content = _generate_pdf_from_document(self.document)
        self.assertIsNone(pdf_content)

    @patch("cases.services._generate_pdf_from_document")
    def test_export_case_documents(self, mock_generate_pdf):
        """Test the case export functionality."""
        # Mock the PDF generation to return simple content
        mock_generate_pdf.return_value = b"mock pdf content"

        # Create a second document for the case
        doc2 = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("doc2.txt", b"content"),
            extracted_text="Some text",
        )

        export_case_documents(self.case.id)

        self.case.refresh_from_db()
        self.assertEqual(self.case.export_status, Case.ExportStatus.COMPLETED)
        self.assertTrue(self.case.export_file.name.endswith(".zip"))

        # Verify the contents of the ZIP file
        zip_path = self.case.export_file.path
        self.assertTrue(os.path.exists(zip_path))

        with zipfile.ZipFile(zip_path, "r") as zf:
            filenames = zf.namelist()
            # Check for original files
            original_file_basename = os.path.basename(
                self.document.original_file.name)
            self.assertIn(
                f"unedited/{original_file_basename}",
                filenames,
            )
            self.assertIn(
                f"unedited/{os.path.basename(doc2.original_file.name)}",
                filenames,
            )
            # Check for redacted PDFs
            self.assertIn(f"redacted/{self.document.filename}.pdf", filenames)
            self.assertIn(f"redacted/{doc2.filename}.pdf", filenames)
            # Check for disclosure PDFs
            self.assertIn(
                f"disclosure/{self.document.filename}.pdf", filenames)
            self.assertIn(f"disclosure/{doc2.filename}.pdf", filenames)

        # Check that the PDF generator was called for each document and mode
        self.assertEqual(mock_generate_pdf.call_count, 4)  # 2 docs * 2 modes

        # Clean up the created export file
        if os.path.exists(zip_path):
            os.remove(zip_path)

    def test_export_case_not_found(self):
        """Test that the export function handles a non-existent case ID."""
        non_existent_id = uuid.uuid4()
        export_case_documents(non_existent_id)
        self.assertFalse(Case.objects.filter(id=non_existent_id).exists())

    def test_find_and_flag_pluralization(self):
        """Test that plural/singular forms are correctly identified."""
        doc2_text = "The party needs to contact other parties."
        doc2 = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("doc2.txt", doc2_text.encode()),
            extracted_text=doc2_text,
            status=Document.Status.READY_FOR_REVIEW,
        )

        # Trigger with the singular form "party"
        source_redaction = Redaction.objects.create(
            document=self.document,
            start_char=0, end_char=5, text="party",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
        )

        find_and_flag_matching_text_in_case(source_redaction.id)

        doc2.refresh_from_db()
        self.assertEqual(doc2.redactions.count(), 2)
        redactions = doc2.redactions.order_by('start_char')
        self.assertEqual(redactions[0].text, "party")
        self.assertEqual(redactions[1].text, "parties")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class DeleteOldCasesServiceTest(TestCase):
    """
    Test suite for the `delete_cases_past_retention_date` service function.
    """

    def test_no_cases_due_for_deletion(self):
        """
        Test that the service function correctly handles the case where no
        cases are due for deletion.
        """
        Case.objects.create(
            case_reference="FUTR01",
            data_subject_name="Future Person",
            retention_review_date=timezone.now().date() + relativedelta(days=1)
        )

        with patch('cases.services.logger') as mock_logger:
            result = delete_cases_past_retention_date()
            self.assertEqual(result, 'No cases are due for deletion.')
            self.assertEqual(Case.objects.count(), 1)
            mock_logger.info.assert_called_with(
                'No cases are due for deletion.')

    def test_deletes_case_past_retention_date(self):
        """
        Test that a single case past its retention date is correctly deleted,
        along with its associated files.
        """
        past_date = timezone.now().date() - relativedelta(days=1)
        case_to_delete = Case.objects.create(
            case_reference="PAST01",
            data_subject_name="Past Person",
            retention_review_date=past_date
        )

        doc_file = SimpleUploadedFile("test_doc.txt", b"some content")
        doc = Document.objects.create(
            case=case_to_delete,
            original_file=doc_file
        )
        self.assertTrue(os.path.exists(doc.original_file.path))

        export_file = SimpleUploadedFile("export.zip", b"zip content")
        case_to_delete.export_file.save(export_file.name, export_file)
        self.assertTrue(os.path.exists(case_to_delete.export_file.path))

        Case.objects.create(
            case_reference="FUTR02",
            data_subject_name="Future Person 2",
            retention_review_date=timezone.now().date() + relativedelta(
                days=10
            )
        )

        self.assertEqual(Case.objects.count(), 2)
        self.assertEqual(Document.objects.count(), 1)

        with patch('cases.services.logger') as mock_logger:
            result = delete_cases_past_retention_date()
            self.assertEqual(
                result,
                'Successfully deleted 1 case(s): PAST01.'
            )
            mock_logger.info.assert_has_calls([
                call('Found 1 case(s) due for deletion.'),
                call(f'Deleting case PAST01 (Retention Date: {past_date})'),
                call('Successfully deleted case PAST01.')
            ])

        self.assertEqual(Case.objects.count(), 1)
        self.assertFalse(Case.objects.filter(case_reference="PAST01").exists())
        self.assertTrue(Case.objects.filter(
            case_reference="FUTR02").exists())
        self.assertEqual(Document.objects.count(), 0)

    def test_iterator_is_used_for_efficiency(self):
        """
        Verify that the .iterator() method is called on the queryset to ensure
        memory efficiency when dealing with a large number of cases.
        """
        with patch('cases.models.Case.objects.filter') as mock_filter:
            mock_iterator = MagicMock()
            mock_iterator.count.return_value = 0
            mock_filter.return_value.iterator.return_value = mock_iterator

            delete_cases_past_retention_date()

            mock_filter.return_value.iterator.assert_called_once()
