import io
import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import date
from unittest.mock import MagicMock, call, patch

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from pypdf import PdfReader

from training.models import Model as SpacyModel
from training.tests.base import NetworkBlockerMixin

from ..models import Case, Document, DocumentExportSettings, Redaction, RedactionContext
from ..services import (
    _build_export_css,
    _generate_pdf_from_document,
    _matches_data_subject,
    _render_table_with_redactions,
    delete_cases_past_retention_date,
    delete_original_files_past_threshold,
    export_case_documents,
    find_and_flag_matching_text_in_case,
    process_document_and_create_redactions,
)

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ServiceTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        """Set up test data for all service tests."""
        self.user = User.objects.create_user(username="testuser", password="password")
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
            status=Document.Status.PROCESSING,
        )
        self.spacy_model = SpacyModel.objects.create(name="en_test_model", is_active=True)

    def tearDown(self):
        """Clean up the temporary media directory."""
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    @patch("cases.services.extract_entities_from_text")
    @patch("cases.services.SpanCatModelManager")
    @patch("cases.services.GLiNERModelManager")
    def test_process_document_and_create_redactions_success(
        self, mock_gliner_manager, mock_spancat_manager, mock_extract_entities
    ):
        """Test successful processing of a document and
        creation of redactions with correct redaction types from entity labels."""
        mock_gliner_instance = MagicMock()
        mock_gliner_manager.get_instance.return_value = mock_gliner_instance

        mock_spancat_instance = MagicMock()
        mock_spancat_instance.get_model_entry.return_value = self.spacy_model
        mock_spancat_manager.get_instance.return_value = mock_spancat_instance

        # Mock the entity extraction with different entity labels
        extracted_text = "This text contains PII like a name and operational data."
        suggestions = [
            {"start_char": 18, "end_char": 21, "text": "PII", "label": "THIRD_PARTY"},
            {"start_char": 29, "end_char": 33, "text": "name", "label": "DS_INFORMATION"},
            {"start_char": 38, "end_char": 54, "text": "operational data", "label": "OPERATIONAL"},
        ]
        mock_extract_entities.return_value = (extracted_text, suggestions, [], None)

        process_document_and_create_redactions(self.document.id)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.READY_FOR_REVIEW)
        self.assertEqual(self.document.extracted_text, extracted_text)
        self.assertEqual(self.document.extracted_tables, [])
        self.assertEqual(self.document.spacy_model, self.spacy_model)
        self.assertEqual(self.document.redactions.count(), 3)

        redactions = list(self.document.redactions.order_by("start_char"))

        # First redaction: THIRD_PARTY -> THIRD_PARTY_PII
        self.assertEqual(redactions[0].text, "PII")
        self.assertEqual(redactions[0].redaction_type, Redaction.RedactionType.THIRD_PARTY_PII)
        self.assertTrue(redactions[0].is_suggestion)
        self.assertFalse(redactions[0].is_accepted)

        # Second redaction: DS_INFORMATION -> DS_INFORMATION
        self.assertEqual(redactions[1].text, "name")
        self.assertEqual(redactions[1].redaction_type, Redaction.RedactionType.DS_INFORMATION)

        # Third redaction: OPERATIONAL -> OPERATIONAL_DATA
        self.assertEqual(redactions[2].text, "operational data")
        self.assertEqual(redactions[2].redaction_type, Redaction.RedactionType.OPERATIONAL_DATA)

        mock_extract_entities.assert_called_once_with(self.document.original_file.path)

    @patch("cases.services.extract_entities_from_text")
    @patch("cases.services.SpanCatModelManager")
    @patch("cases.services.GLiNERModelManager")
    def test_process_document_unknown_label_uses_fallback(
        self, mock_gliner_manager, mock_spancat_manager, mock_extract_entities
    ):
        """Test that unknown entity labels fall back to THIRD_PARTY_PII."""
        mock_gliner_manager.get_instance.return_value = MagicMock()
        mock_spancat_manager.get_instance.return_value = MagicMock(get_model_entry=MagicMock(return_value=None))

        extracted_text = "This has an unknown entity."
        suggestions = [
            {"start_char": 12, "end_char": 19, "text": "unknown", "label": "UNKNOWN_TYPE"},
        ]
        mock_extract_entities.return_value = (extracted_text, suggestions, [], None)

        process_document_and_create_redactions(self.document.id)

        self.document.refresh_from_db()
        self.assertEqual(self.document.redactions.count(), 1)

        redaction = self.document.redactions.first()
        self.assertEqual(redaction.redaction_type, Redaction.RedactionType.THIRD_PARTY_PII)

    @patch("cases.services.SpanCatModelManager")
    @patch("cases.services.GLiNERModelManager")
    @patch("cases.services.extract_entities_from_text")
    def test_process_document_extraction_fails(self, mock_extract_entities, mock_gliner_manager, mock_spancat_manager):
        """Test document processing when text extraction returns nothing."""
        mock_extract_entities.return_value = (None, [], [], None)
        mock_gliner_manager.get_instance.return_value = MagicMock()
        mock_spancat_manager.get_instance.return_value = MagicMock(get_model_entry=MagicMock(return_value=None))

        process_document_and_create_redactions(self.document.id)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.ERROR)
        self.assertIsNone(self.document.extracted_text)
        self.assertEqual(self.document.redactions.count(), 0)

    def test_process_document_aborts_if_not_processing(self):
        """Test that the task aborts early if the document status is no longer PROCESSING."""
        self.document.status = Document.Status.UNPROCESSED
        self.document.save()

        process_document_and_create_redactions(self.document.id)

        self.document.refresh_from_db()
        # Status should remain UNPROCESSED — not changed by the task
        self.assertEqual(self.document.status, Document.Status.UNPROCESSED)
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
        self.assertEqual(new_redactions[0].redaction_type, Redaction.RedactionType.DS_INFORMATION)
        self.assertTrue(new_redactions[0].is_suggestion)

        self.assertEqual(new_redactions[1].text, "name")
        self.assertEqual(new_redactions[1].redaction_type, Redaction.RedactionType.DS_INFORMATION)

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
        self.assertEqual(existing_redaction.redaction_type, Redaction.RedactionType.DS_INFORMATION)
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
        pdf_content_disclosure = _generate_pdf_from_document(self.document, mode="disclosure")
        self.assertIsNotNone(pdf_content_disclosure)
        self.assertIsInstance(pdf_content_disclosure, bytes)
        # A simple check to see if the PDF content seems valid
        self.assertTrue(pdf_content_disclosure.startswith(b"%PDF-"))

        # Test redacted mode (color highlight)
        pdf_content_redacted = _generate_pdf_from_document(self.document, mode="redacted")
        self.assertIsNotNone(pdf_content_redacted)
        self.assertIsInstance(pdf_content_redacted, bytes)
        self.assertTrue(pdf_content_redacted.startswith(b"%PDF-"))

    def test_generate_pdf_disclosure_excludes_ds_information(self):
        """DS_INFORMATION redactions must not be blacked out in the disclosure PDF."""
        self.document.extracted_text = "John Doe attended the event on 01/01/1990."
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=8,
            text="John Doe",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
            is_accepted=True,
        )

        pdf_content = _generate_pdf_from_document(self.document, mode="disclosure")
        self.assertIsNotNone(pdf_content)

        page_text = PdfReader(io.BytesIO(pdf_content)).pages[0].extract_text()
        self.assertIn("John Doe", page_text)

    def test_generate_pdf_redacted_includes_ds_information(self):
        """DS_INFORMATION redactions should still be highlighted in the redacted (review) PDF."""
        self.document.extracted_text = "John Doe attended the event."
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=8,
            text="John Doe",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
            is_accepted=True,
        )

        pdf_content = _generate_pdf_from_document(self.document, mode="redacted")
        self.assertIsNotNone(pdf_content)
        self.assertTrue(pdf_content.startswith(b"%PDF-"))

    def test_generate_pdf_with_redaction_context(self):
        """
        Test that redaction context text appears in the final disclosure PDF.
        """
        self.document.extracted_text = "The secret ingredient is PII."
        self.document.save()
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=25,
            end_char=28,
            text="PII",
            is_accepted=True,
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        context_text = "a type of cheese"
        RedactionContext.objects.create(redaction=redaction, text=context_text)

        pdf_content = _generate_pdf_from_document(self.document, mode="disclosure")

        self.assertIsNotNone(pdf_content)
        self.assertTrue(pdf_content.startswith(b"%PDF-"))

        bytes_content = io.BytesIO(pdf_content)
        pdf = PdfReader(bytes_content)
        page_text = pdf.pages[0].extract_text()
        self.assertIn(context_text, page_text)

    def test_generate_pdf_redacts_hash_prefix_not_in_stored_span(self):
        """
        A '#' immediately before a stored redaction span should be redacted in the PDF
        even if the span itself does not include it (handles documents processed before
        the extraction-layer fix).
        """
        self.document.extracted_text = "Crime ref #42/12345/24 was recorded."
        self.document.save()
        # Stored span starts at 11 (the '4'), not 10 (the '#')
        Redaction.objects.create(
            document=self.document,
            start_char=11,
            end_char=22,
            text="42/12345/24",
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
            is_accepted=True,
        )

        pdf_content = _generate_pdf_from_document(self.document, mode="disclosure")
        self.assertIsNotNone(pdf_content)
        bytes_content = io.BytesIO(pdf_content)
        pdf = PdfReader(bytes_content)
        page_text = pdf.pages[0].extract_text()
        # The '#' and the crime ref should both be absent from the extracted text
        self.assertNotIn("#42/12345/24", page_text)
        self.assertNotIn("#", page_text)

    def test_generate_pdf_no_text(self):
        """Test PDF generation for a document with no extracted text."""
        self.document.extracted_text = ""
        self.document.save()
        pdf_content = _generate_pdf_from_document(self.document)
        self.assertIsNone(pdf_content)

    def test_generate_pdf_with_custom_font(self):
        """Test that PDF generation works with a non-default font family."""
        self.document.extracted_text = "Some text for font testing."
        self.document.save()
        settings = DocumentExportSettings.get()
        settings.font_family = DocumentExportSettings.FontFamily.TIMES_NEW_ROMAN
        settings.save()

        pdf_content = _generate_pdf_from_document(self.document, mode="disclosure")
        self.assertIsNotNone(pdf_content)
        self.assertIsInstance(pdf_content, bytes)
        self.assertTrue(pdf_content.startswith(b"%PDF-"))

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
            original_file_basename = os.path.basename(self.document.original_file.name)
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
            self.assertIn(f"disclosure/{self.document.filename}.pdf", filenames)
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
            start_char=0,
            end_char=5,
            text="party",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
        )

        find_and_flag_matching_text_in_case(source_redaction.id)

        doc2.refresh_from_db()
        self.assertEqual(doc2.redactions.count(), 2)
        redactions = doc2.redactions.order_by("start_char")
        self.assertEqual(redactions[0].text, "party")
        self.assertEqual(redactions[1].text, "parties")

    @patch("cases.services.extract_entities_from_text")
    @patch("cases.services.SpanCatModelManager")
    @patch("cases.services.GLiNERModelManager")
    def test_process_document_filters_data_subject_entities(
        self, mock_gliner_manager, mock_spancat_manager, mock_extract_entities
    ):
        """Test that entities matching the data subject name/DOB are excluded."""
        mock_gliner_manager.get_instance.return_value = MagicMock()
        mock_spancat_manager.get_instance.return_value = MagicMock(get_model_entry=MagicMock(return_value=None))

        extracted_text = "John Doe lives in London. DOB: 01/01/1990."
        suggestions = [
            {"start_char": 0, "end_char": 8, "text": "John Doe", "label": "THIRD_PARTY"},
            {"start_char": 18, "end_char": 24, "text": "London", "label": "THIRD_PARTY"},
            {"start_char": 31, "end_char": 41, "text": "01/01/1990", "label": "THIRD_PARTY"},
        ]
        mock_extract_entities.return_value = (extracted_text, suggestions, [], None)

        process_document_and_create_redactions(self.document.id)

        self.document.refresh_from_db()
        # "John Doe" (full name match) and "01/01/1990" (DOB match) should be filtered out
        self.assertEqual(self.document.redactions.count(), 1)
        redaction = self.document.redactions.first()
        self.assertEqual(redaction.text, "London")

    def test_matches_data_subject_full_name(self):
        """Test full name matching (case-insensitive, bidirectional)."""
        self.assertTrue(_matches_data_subject("John Doe", self.case))
        self.assertTrue(_matches_data_subject("john doe", self.case))
        self.assertTrue(_matches_data_subject("JOHN DOE", self.case))

    def test_matches_data_subject_name_parts(self):
        """Test individual name parts match."""
        self.assertTrue(_matches_data_subject("John", self.case))
        self.assertTrue(_matches_data_subject("Doe", self.case))

    def test_matches_data_subject_no_match(self):
        """Test non-matching text."""
        self.assertFalse(_matches_data_subject("Jane Smith", self.case))
        self.assertFalse(_matches_data_subject("London", self.case))

    def test_matches_data_subject_dob_formats(self):
        """Test DOB matching across various date formats."""
        self.assertTrue(_matches_data_subject("01/01/1990", self.case))
        self.assertTrue(_matches_data_subject("01-01-1990", self.case))
        self.assertTrue(_matches_data_subject("1990-01-01", self.case))
        self.assertTrue(_matches_data_subject("1 January 1990", self.case))
        self.assertTrue(_matches_data_subject("01 January 1990", self.case))
        self.assertTrue(_matches_data_subject("1 Jan 1990", self.case))

    def test_matches_data_subject_no_dob(self):
        """Test with a case that has no DOB."""
        case_no_dob = Case.objects.create(
            case_reference="250002",
            data_subject_name="Alice Test",
            created_by=self.user,
        )
        self.assertTrue(_matches_data_subject("Alice", case_no_dob))
        self.assertFalse(_matches_data_subject("01/01/1990", case_no_dob))

    def test_matches_data_subject_empty_text(self):
        """Test with empty/whitespace text."""
        self.assertFalse(_matches_data_subject("", self.case))
        self.assertFalse(_matches_data_subject("   ", self.case))

    def test_matches_data_subject_single_char_name_part_ignored(self):
        """Test that single-character name parts are not matched."""
        case = Case.objects.create(
            case_reference="250003",
            data_subject_name="A Smith",
            created_by=self.user,
        )
        # "A" is a single char, should not match
        self.assertFalse(_matches_data_subject("A", case))
        # "Smith" should match
        self.assertTrue(_matches_data_subject("Smith", case))


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class DeleteOldCasesServiceTest(NetworkBlockerMixin, TestCase):
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
            retention_review_date=timezone.now().date() + relativedelta(days=1),
        )

        with patch("cases.services.logger") as mock_logger:
            result = delete_cases_past_retention_date()
            self.assertEqual(result, "No cases are due for deletion.")
            self.assertEqual(Case.objects.count(), 1)
            mock_logger.info.assert_called_with("No cases are due for deletion.")

    def test_deletes_case_past_retention_date(self):
        """
        Test that a single case past its retention date is correctly deleted,
        along with its associated files.
        """
        past_date = timezone.now().date() - relativedelta(days=1)
        case_to_delete = Case.objects.create(
            case_reference="PAST01", data_subject_name="Past Person", retention_review_date=past_date
        )

        doc_file = SimpleUploadedFile("test_doc.txt", b"some content")
        doc = Document.objects.create(case=case_to_delete, original_file=doc_file)
        self.assertTrue(os.path.exists(doc.original_file.path))

        export_file = SimpleUploadedFile("export.zip", b"zip content")
        case_to_delete.export_file.save(export_file.name, export_file)
        self.assertTrue(os.path.exists(case_to_delete.export_file.path))

        Case.objects.create(
            case_reference="FUTR02",
            data_subject_name="Future Person 2",
            retention_review_date=timezone.now().date() + relativedelta(days=10),
        )

        self.assertEqual(Case.objects.count(), 2)
        self.assertEqual(Document.objects.count(), 1)

        with patch("cases.services.logger") as mock_logger:
            result = delete_cases_past_retention_date()
            self.assertEqual(result, "Successfully deleted 1 case(s): PAST01.")
            mock_logger.info.assert_has_calls(
                [
                    call("Found 1 case(s) due for deletion."),
                    call(f"Deleting case PAST01 (Retention Date: {past_date})"),
                    call("Successfully deleted case PAST01."),
                ]
            )

        self.assertEqual(Case.objects.count(), 1)
        self.assertFalse(Case.objects.filter(case_reference="PAST01").exists())
        self.assertTrue(Case.objects.filter(case_reference="FUTR02").exists())
        self.assertEqual(Document.objects.count(), 0)

    def test_iterator_is_used_for_efficiency(self):
        """
        Verify that the .iterator() method is called on the queryset to ensure
        memory efficiency when dealing with a large number of cases.
        """
        with patch("cases.models.Case.objects.filter") as mock_filter:
            mock_iterator = MagicMock()
            mock_iterator.count.return_value = 0
            mock_filter.return_value.iterator.return_value = mock_iterator

            delete_cases_past_retention_date()

            mock_filter.return_value.iterator.assert_called_once()


class BuildExportCssTests(NetworkBlockerMixin, TestCase):
    def _make_settings(self, **kwargs):
        defaults = {
            "header_text": "",
            "footer_text": "",
            "watermark_text": "",
            "watermark_include_case_ref": False,
            "page_numbers_enabled": False,
        }
        defaults.update(kwargs)
        obj = DocumentExportSettings(**defaults)
        return obj

    def test_defaults_no_header_footer_page_numbers(self):
        css = _build_export_css(self._make_settings())
        self.assertIn("margin: 2cm 2cm 2cm 2cm", css)
        self.assertNotIn("@top-center", css)
        self.assertNotIn("@bottom-center", css)
        self.assertNotIn("watermark", css)

    def test_header_increases_top_margin_and_zeroes_companions(self):
        css = _build_export_css(self._make_settings(header_text="OFFICIAL"))
        self.assertIn("margin: 2.5cm 2cm 2cm 2cm", css)
        self.assertIn("@top-center", css)
        self.assertIn("OFFICIAL", css)
        self.assertIn("@top-left", css)
        self.assertIn("@top-right", css)

    def test_footer_increases_bottom_margin_and_zeroes_companions(self):
        css = _build_export_css(self._make_settings(footer_text="Confidential"))
        self.assertIn("margin: 2cm 2cm 2.5cm 2cm", css)
        self.assertIn("@bottom-center", css)
        self.assertIn("Confidential", css)
        self.assertIn("@bottom-left", css)
        self.assertIn("@bottom-right", css)

    def test_page_numbers_in_output(self):
        css = _build_export_css(self._make_settings(page_numbers_enabled=True))
        self.assertIn("counter(page)", css)
        self.assertIn("counter(pages)", css)
        self.assertIn("@bottom-center", css)

    def test_footer_and_page_numbers_combined_in_bottom_center(self):
        css = _build_export_css(self._make_settings(footer_text="Confidential", page_numbers_enabled=True))
        self.assertIn("@bottom-center", css)
        self.assertIn("Confidential", css)
        self.assertIn("counter(page)", css)
        self.assertIn(r"\A", css)

    def test_watermark_css_emitted_when_watermark_text_set(self):
        css = _build_export_css(
            self._make_settings(watermark_text="SAR", watermark_include_case_ref=True),
            case_reference="2025-001",
        )
        self.assertIn(".watermark", css)
        self.assertIn("rotate(-45deg)", css)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class GeneratePdfWithSettingsTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(case_reference="CSS01", data_subject_name="Test User")
        file = SimpleUploadedFile("doc.txt", b"Hello world redacted text here")
        self.document = Document.objects.create(
            case=self.case,
            original_file=file,
            extracted_text="Hello world redacted text here",
        )

    def test_generate_pdf_with_non_default_settings(self):
        settings = DocumentExportSettings(
            header_text="OFFICIAL",
            footer_text="Confidential",
            watermark_text="DRAFT",
            watermark_include_case_ref=False,
            page_numbers_enabled=True,
        )
        result = _generate_pdf_from_document(self.document, mode="disclosure", export_settings=settings)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result[:4] == b"%PDF")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ExportCaseDocumentsPassesSettingsTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(case_reference="EXP01", data_subject_name="Export User")
        file = SimpleUploadedFile("doc.txt", b"Some text")
        self.document = Document.objects.create(
            case=self.case,
            original_file=file,
            extracted_text="Some text",
            status=Document.Status.COMPLETED,
        )

    def test_export_case_documents_passes_settings_and_case_ref(self):
        mock_settings = DocumentExportSettings(
            header_text="HDR",
            footer_text="FTR",
            watermark_text="WM",
            watermark_include_case_ref=True,
            page_numbers_enabled=True,
        )
        with (
            patch("cases.services.DocumentExportSettings.get", return_value=mock_settings) as mock_get,
            patch("cases.services._generate_pdf_from_document", return_value=b"%PDF-test") as mock_gen,
        ):
            export_case_documents(self.case.id)

        mock_get.assert_called_once()
        calls = mock_gen.call_args_list
        self.assertEqual(len(calls), 2)
        for c in calls:
            self.assertEqual(c.kwargs["export_settings"], mock_settings)
            self.assertEqual(c.kwargs["case_reference"], "EXP01")


def _make_redaction(start, end, redaction_type="PII"):
    r = MagicMock()
    r.start_char = start
    r.end_char = end
    r.redaction_type = redaction_type
    del r.context  # ensure hasattr(r, "context") is False by default
    return r


class RenderTableWithRedactionsTests(NetworkBlockerMixin, TestCase):
    def _cell(self, row, col, start, end, text, **kwargs):
        c = {"row": row, "col": col, "start": start, "end": end, "text": text}
        c.update(kwargs)
        return c

    def test_no_cells_returns_escaped_text(self):
        result = _render_table_with_redactions({"text": "plain <text>"}, "", [], "internal")
        self.assertEqual(result, "plain &lt;text&gt;")

    def test_no_cells_empty_text_returns_empty_string(self):
        result = _render_table_with_redactions({}, "", [], "internal")
        self.assertEqual(result, "")

    def test_simple_table_structure(self):
        full_text = "Hello World"
        table_data = {
            "cells": [
                self._cell(0, 0, 0, 5, "Hello", isMergedContinuation=False, colspan=1, rowspan=1),
                self._cell(0, 1, 6, 11, "World", isMergedContinuation=False, colspan=1, rowspan=1),
            ]
        }
        result = _render_table_with_redactions(table_data, full_text, [], "internal")
        self.assertIn("<table", result)
        self.assertIn("<tr>", result)
        self.assertIn("Hello", result)
        self.assertIn("World", result)

    def test_redaction_applied_within_cell(self):
        full_text = "Hello World"
        table_data = {
            "cells": [
                self._cell(0, 0, 0, 5, "Hello", isMergedContinuation=False, colspan=1, rowspan=1),
                self._cell(0, 1, 6, 11, "World", isMergedContinuation=False, colspan=1, rowspan=1),
            ]
        }
        redaction = _make_redaction(6, 11)
        result = _render_table_with_redactions(table_data, full_text, [redaction], "internal")
        self.assertIn('class="redaction', result)
        self.assertIn("World", result)

    def test_disclosure_mode_replaces_with_blocks(self):
        full_text = "Secret data"
        table_data = {
            "cells": [
                self._cell(0, 0, 0, 6, "Secret", isMergedContinuation=False, colspan=1, rowspan=1),
                self._cell(0, 1, 7, 11, "data", isMergedContinuation=False, colspan=1, rowspan=1),
            ]
        }
        redaction = _make_redaction(0, 6)
        result = _render_table_with_redactions(table_data, full_text, [redaction], "disclosure")
        self.assertIn("█", result)
        self.assertNotIn("Secret", result)

    def test_merged_continuation_cell_skipped(self):
        full_text = "MergedMerged"
        table_data = {
            "cells": [
                self._cell(0, 0, 0, 6, "Merged", isMergedContinuation=False, colspan=2, rowspan=1),
                self._cell(0, 1, 0, 6, "Merged", isMergedContinuation=True, colspan=1, rowspan=1),
            ]
        }
        result = _render_table_with_redactions(table_data, full_text, [], "internal")
        # Only one <td> should be rendered (the continuation is skipped)
        self.assertEqual(result.count("<td"), 1)
        self.assertIn('colspan="2"', result)

    def test_colspan_and_rowspan_attrs_rendered(self):
        full_text = "AB"
        table_data = {
            "cells": [
                self._cell(0, 0, 0, 1, "A", isMergedContinuation=False, colspan=3, rowspan=2),
            ]
        }
        result = _render_table_with_redactions(table_data, full_text, [], "internal")
        self.assertIn('colspan="3"', result)
        self.assertIn('rowspan="2"', result)

    def test_col_widths_applied(self):
        full_text = "AB"
        table_data = {
            "cells": [self._cell(0, 0, 0, 1, "A", isMergedContinuation=False, colspan=1, rowspan=1)],
            "colWidths": [42.5],
        }
        result = _render_table_with_redactions(table_data, full_text, [], "internal")
        self.assertIn("width: 42.5%", result)

    def test_equal_fallback_widths_when_no_col_widths(self):
        full_text = "AB"
        table_data = {
            "cells": [
                self._cell(0, 0, 0, 1, "A", isMergedContinuation=False, colspan=1, rowspan=1),
                self._cell(0, 1, 1, 2, "B", isMergedContinuation=False, colspan=1, rowspan=1),
            ]
        }
        result = _render_table_with_redactions(table_data, full_text, [], "internal")
        self.assertIn("width: 50.0%", result)

    def test_heuristic_merge_detection_for_legacy_data(self):
        # No isMergedContinuation key — heuristic should detect adjacent identical cells
        full_text = "SameSame"
        table_data = {
            "cells": [
                {"row": 0, "col": 0, "start": 0, "end": 4, "text": "Same"},
                {"row": 0, "col": 1, "start": 0, "end": 4, "text": "Same"},
            ]
        }
        result = _render_table_with_redactions(table_data, full_text, [], "internal")
        self.assertEqual(result.count("<td"), 1)
        self.assertIn('colspan="2"', result)

    def test_heuristic_no_merge_for_different_adjacent_cells(self):
        full_text = "AB"
        table_data = {
            "cells": [
                {"row": 0, "col": 0, "start": 0, "end": 1, "text": "A"},
                {"row": 0, "col": 1, "start": 1, "end": 2, "text": "B"},
            ]
        }
        result = _render_table_with_redactions(table_data, full_text, [], "internal")
        self.assertEqual(result.count("<td"), 2)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DeleteOriginalFilesTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="DEL01",
            data_subject_name="Delete Test",
            status=Case.Status.COMPLETED,
        )
        self.document = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("test.txt", b"content"),
            status=Document.Status.COMPLETED,
        )

    @override_settings(DELETE_ORIGINAL_FILES=False)
    def test_disabled_returns_early(self):
        result = delete_original_files_past_threshold()
        self.assertEqual(result, "Original file deletion is disabled.")
        self.document.refresh_from_db()
        self.assertTrue(bool(self.document.original_file))

    @override_settings(DELETE_ORIGINAL_FILES=True, DELETE_ORIGINAL_FILES_AFTER_DAYS=30)
    def test_within_threshold_not_deleted(self):
        # Case updated_at is effectively "now" — within 30 days
        result = delete_original_files_past_threshold()
        self.assertEqual(result, "Deleted original files for 0 document(s).")
        self.document.refresh_from_db()
        self.assertTrue(bool(self.document.original_file))

    @override_settings(DELETE_ORIGINAL_FILES=True, DELETE_ORIGINAL_FILES_AFTER_DAYS=0)
    def test_past_threshold_deletes_original_file(self):
        result = delete_original_files_past_threshold()
        self.assertEqual(result, "Deleted original files for 1 document(s).")
        self.document.refresh_from_db()
        self.assertFalse(bool(self.document.original_file))

    @override_settings(DELETE_ORIGINAL_FILES=True, DELETE_ORIGINAL_FILES_AFTER_DAYS=0)
    def test_non_terminal_case_not_deleted(self):
        self.case.status = Case.Status.OPEN
        self.case.save()
        result = delete_original_files_past_threshold()
        self.assertEqual(result, "Deleted original files for 0 document(s).")
        self.document.refresh_from_db()
        self.assertTrue(bool(self.document.original_file))
