import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from training.models import Model as SpacyModel
from training.tests.base import NetworkBlockerMixin

from ..models import (
    Case,
    Document,
    DocumentExportSettings,
    InternalReview,
    Redaction,
    RedactionContext,
    RedactionSnapshot,
    ReviewWorkflowSettings,
)
from ..services import (
    _apply_case_ds_info_to_document,
    _apply_existing_case_decisions,
    _build_document_html,
    _build_export_css,
    _cell_fully_redacted,
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
        extracted_text = (
            "This text contains PII like a name and operational data."
        )
        suggestions = [
            {
                "start_char": 18,
                "end_char": 21,
                "text": "PII",
                "label": "THIRD_PARTY",
            },
            {
                "start_char": 29,
                "end_char": 33,
                "text": "name",
                "label": "DS_INFORMATION",
            },
            {
                "start_char": 38,
                "end_char": 54,
                "text": "operational data",
                "label": "OPERATIONAL",
            },
        ]
        mock_extract_entities.return_value = (
            extracted_text,
            suggestions,
            [],
            None,
        )

        process_document_and_create_redactions(self.document.id)

        self.document.refresh_from_db()
        self.assertEqual(
            self.document.status, Document.Status.READY_FOR_REVIEW
        )
        self.assertEqual(self.document.extracted_text, extracted_text)
        self.assertEqual(self.document.extracted_tables, [])
        self.assertEqual(self.document.spacy_model, self.spacy_model)
        self.assertEqual(self.document.redactions.count(), 3)

        redactions = list(self.document.redactions.order_by("start_char"))

        # First redaction: THIRD_PARTY -> THIRD_PARTY_PII
        self.assertEqual(redactions[0].text, "PII")
        self.assertEqual(
            redactions[0].redaction_type,
            Redaction.RedactionType.THIRD_PARTY_PII,
        )
        self.assertTrue(redactions[0].is_suggestion)
        self.assertFalse(redactions[0].is_accepted)

        # Second redaction: DS_INFORMATION -> DS_INFORMATION
        self.assertEqual(redactions[1].text, "name")
        self.assertEqual(
            redactions[1].redaction_type,
            Redaction.RedactionType.DS_INFORMATION,
        )

        # Third redaction: OPERATIONAL -> OPERATIONAL_DATA
        self.assertEqual(redactions[2].text, "operational data")
        self.assertEqual(
            redactions[2].redaction_type,
            Redaction.RedactionType.OPERATIONAL_DATA,
        )

        mock_extract_entities.assert_called_once_with(
            self.document.original_file.path,
            data_subject_name="John Doe",
            data_subject_dob=date(1990, 1, 1),
        )

    @patch("cases.services.extract_entities_from_text")
    @patch("cases.services.SpanCatModelManager")
    @patch("cases.services.GLiNERModelManager")
    def test_machine_decisions_during_processing_never_trainable(
        self, mock_gliner_manager, mock_spancat_manager, mock_extract_entities
    ):
        """End-to-end regression test for the propagation training leak:
        with auto-accept on and case propagation firing, no redaction from
        processing may enter the SpanCat training selection."""
        settings = ReviewWorkflowSettings.get()
        settings.auto_accept_enabled = True
        settings.save()

        # A prior human accept in another document of the same case, so
        # case-decision propagation fires for "operational data".
        prior_doc = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile(
                "prior.pdf", b"prior", "application/pdf"
            ),
            status=Document.Status.COMPLETED,
        )
        Redaction.objects.create(
            document=prior_doc,
            start_char=0,
            end_char=16,
            text="operational data",
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )

        mock_gliner_manager.get_instance.return_value = MagicMock()
        mock_spancat_manager.get_instance.return_value = MagicMock(
            get_model_entry=MagicMock(return_value=self.spacy_model)
        )
        mock_extract_entities.return_value = (
            "This text contains operational data.",
            [
                {
                    "start_char": 19,
                    "end_char": 35,
                    "text": "operational data",
                    "label": "OPERATIONAL",
                },
            ],
            [],
            None,
        )

        process_document_and_create_redactions(self.document.id)

        new_redactions = self.document.redactions.all()
        self.assertTrue(new_redactions.exists())
        for redaction in new_redactions:
            self.assertTrue(redaction.is_accepted)
            self.assertTrue(redaction.auto_accepted)
            self.assertNotEqual(
                redaction.decided_by, Redaction.DecidedBy.HUMAN
            )
        self.assertQuerySetEqual(new_redactions.trainable(), [])

    @patch("cases.services.extract_entities_from_text")
    @patch("cases.services.SpanCatModelManager")
    @patch("cases.services.GLiNERModelManager")
    def test_process_document_unknown_label_uses_fallback(
        self, mock_gliner_manager, mock_spancat_manager, mock_extract_entities
    ):
        """Test that unknown entity labels fall back to THIRD_PARTY_PII."""
        mock_gliner_manager.get_instance.return_value = MagicMock()
        mock_spancat_manager.get_instance.return_value = MagicMock(
            get_model_entry=MagicMock(return_value=None)
        )

        extracted_text = "This has an unknown entity."
        suggestions = [
            {
                "start_char": 12,
                "end_char": 19,
                "text": "unknown",
                "label": "UNKNOWN_TYPE",
            },
        ]
        mock_extract_entities.return_value = (
            extracted_text,
            suggestions,
            [],
            None,
        )

        process_document_and_create_redactions(self.document.id)

        self.document.refresh_from_db()
        self.assertEqual(self.document.redactions.count(), 1)

        redaction = self.document.redactions.first()
        self.assertEqual(
            redaction.redaction_type, Redaction.RedactionType.THIRD_PARTY_PII
        )

    @patch("cases.services.SpanCatModelManager")
    @patch("cases.services.GLiNERModelManager")
    @patch("cases.services.extract_entities_from_text")
    def test_process_document_extraction_fails(
        self, mock_extract_entities, mock_gliner_manager, mock_spancat_manager
    ):
        """Test document processing when text extraction returns nothing."""
        mock_extract_entities.return_value = (None, [], [], None)
        mock_gliner_manager.get_instance.return_value = MagicMock()
        mock_spancat_manager.get_instance.return_value = MagicMock(
            get_model_entry=MagicMock(return_value=None)
        )

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
        self.assertEqual(
            new_redactions[0].redaction_type,
            Redaction.RedactionType.DS_INFORMATION,
        )
        self.assertTrue(new_redactions[0].is_suggestion)

        self.assertEqual(new_redactions[1].text, "name")
        self.assertEqual(
            new_redactions[1].redaction_type,
            Redaction.RedactionType.DS_INFORMATION,
        )

    def test_build_document_html_contains_redaction_span(self):
        """Accepted redacted text produces a redaction span in both modes."""
        self.document.extracted_text = "This is some text with PII to redact."
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=23,
            end_char=26,
            text="PII",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )

        html_disclosure, _ = _build_document_html(
            self.document, mode="disclosure"
        )
        self.assertIsNotNone(html_disclosure)
        self.assertIn('class="redaction', html_disclosure)

        html_redacted, _ = _build_document_html(self.document, mode="redacted")
        self.assertIsNotNone(html_redacted)
        self.assertIn('class="redaction', html_redacted)

    def test_build_document_html_disclosure_excludes_ds_information(self):
        """DS_INFORMATION spans must not receive redaction markup in disclosure mode."""
        self.document.extracted_text = (
            "John Doe attended the event on 01/01/1990."
        )
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=8,
            text="John Doe",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )

        html, _ = _build_document_html(self.document, mode="disclosure")
        self.assertIsNotNone(html)
        self.assertIn("John Doe", html)
        self.assertNotIn('class="redaction', html)

    def test_build_document_html_removal_excludes_ds_information(self):
        """DS_INFORMATION text survives removal mode; other redactions are removed."""
        self.document.extracted_text = (
            "John Doe attended the event with Jane Smith."
        )
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=8,
            text="John Doe",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        Redaction.objects.create(
            document=self.document,
            start_char=33,
            end_char=43,
            text="Jane Smith",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )

        html, _ = _build_document_html(self.document, mode="removal")
        self.assertIsNotNone(html)
        self.assertIn("John Doe", html)
        self.assertNotIn("Jane Smith", html)
        self.assertIn("[...]", html)

    def test_build_document_html_removal_excludes_ds_information_prefetched(
        self,
    ):
        """The prefetched-redactions branch also keeps DS_INFORMATION in removal mode."""
        self.document.extracted_text = (
            "John Doe attended the event with Jane Smith."
        )
        self.document.save()
        ds_info = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=8,
            text="John Doe",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        pii = Redaction.objects.create(
            document=self.document,
            start_char=33,
            end_char=43,
            text="Jane Smith",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        self.document.accepted_redactions_prefetched = [ds_info, pii]

        html, _ = _build_document_html(self.document, mode="removal")
        self.assertIsNotNone(html)
        self.assertIn("John Doe", html)
        self.assertNotIn("Jane Smith", html)
        self.assertIn("[...]", html)

    def test_build_document_html_redacted_includes_ds_information(self):
        """DS_INFORMATION spans should still be marked up in redacted (review) mode."""
        self.document.extracted_text = "John Doe attended the event."
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=8,
            text="John Doe",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )

        html, _ = _build_document_html(self.document, mode="redacted")
        self.assertIsNotNone(html)
        self.assertIn('class="redaction', html)

    def test_build_document_html_includes_redaction_context(self):
        """Redaction context text must appear in the disclosure HTML."""
        self.document.extracted_text = "The secret ingredient is PII."
        self.document.save()
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=25,
            end_char=28,
            text="PII",
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        context_text = "a type of cheese"
        RedactionContext.objects.create(redaction=redaction, text=context_text)

        html, _ = _build_document_html(self.document, mode="disclosure")
        self.assertIsNotNone(html)
        self.assertIn(context_text, html)

    def test_build_document_html_redacts_hash_prefix_not_in_stored_span(self):
        """A '#' immediately before a stored span should be included in the redaction markup."""
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
            decided_by=Redaction.DecidedBy.HUMAN,
        )

        html, _ = _build_document_html(self.document, mode="disclosure")
        self.assertIsNotNone(html)
        # The crime ref text should not appear outside a redaction span
        self.assertNotIn(">42/12345/24<", html)
        self.assertNotIn(">#42/12345/24<", html)

    def test_build_document_html_removal_mode_inline(self):
        """A redaction surrounded by text on both sides keeps its [...] marker."""
        self.document.extracted_text = "The suspect John was arrested."
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=12,
            end_char=16,
            text="John",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        html, _ = _build_document_html(self.document, mode="removal")
        self.assertIsNotNone(html)
        self.assertIn("[...]", html)
        self.assertNotIn("John", html)

    def test_build_document_html_removal_mode_leading_inline_marker_kept(self):
        """A redaction at the start of a sentence (text follows on the same line) keeps [...]."""
        self.document.extracted_text = "John was arrested."
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="John",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        html, _ = _build_document_html(self.document, mode="removal")
        self.assertIsNotNone(html)
        # The marker is inline with " was arrested." on the same line → keep it
        self.assertIn("[...]", html)
        self.assertIn("was arrested", html)

    def test_build_document_html_removal_mode_own_line_marker_suppressed(self):
        """A redaction that occupies its own line (no surrounding text on that line) is dropped."""
        self.document.extracted_text = (
            "Involved persons:\nJohn Smith\nOccurrence log:"
        )
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=18,
            end_char=28,
            text="John Smith",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        html, _ = _build_document_html(self.document, mode="removal")
        self.assertIsNotNone(html)
        self.assertNotIn("[...]", html)
        self.assertIn("Involved persons", html)
        self.assertIn("Occurrence log", html)

    def test_build_document_html_removal_mode_bullet_only_line_suppressed(
        self,
    ):
        """A bullet point whose only content is a redaction is dropped entirely."""
        self.document.extracted_text = (
            "Involved persons:\n• John Smith\n• Jane Doe\nOccurrence log:"
        )
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=20,
            end_char=30,
            text="John Smith",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        Redaction.objects.create(
            document=self.document,
            start_char=33,
            end_char=41,
            text="Jane Doe",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        html, _ = _build_document_html(self.document, mode="removal")
        self.assertIsNotNone(html)
        # Both bullet lines are fully redacted — no [...] should appear
        self.assertNotIn("[...]", html)
        self.assertIn("Involved persons", html)
        self.assertIn("Occurrence log", html)

    def test_build_document_html_removal_mode_isolated_mid_segment_suppressed(
        self,
    ):
        """A lone [...] appearing mid-segment on its own line is dropped."""
        self.document.extracted_text = (
            "Some text here.\nJohn Smith\nMore text below."
        )
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=16,
            end_char=26,
            text="John Smith",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        html, _ = _build_document_html(self.document, mode="removal")
        self.assertIsNotNone(html)
        self.assertNotIn("[...]", html)
        self.assertIn("Some text here", html)
        self.assertIn("More text below", html)

    def test_build_document_html_removal_mode_fully_redacted_block_suppressed(
        self,
    ):
        """A text block that is entirely redacted is omitted in removal mode."""
        self.document.extracted_text = "John Smith"
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=10,
            text="John Smith",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        html, _ = _build_document_html(self.document, mode="removal")
        self.assertIsNotNone(html)
        self.assertNotIn("[...]", html)

    def test_build_document_html_removal_mode_merges_adjacent_inline(self):
        """Adjacent redactions at the start of a sentence merge to one and are kept inline."""
        self.document.extracted_text = "John Smith was arrested."
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="John",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        Redaction.objects.create(
            document=self.document,
            start_char=5,
            end_char=10,
            text="Smith",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        html, _ = _build_document_html(self.document, mode="removal")
        # Merged into one inline marker; " was arrested" follows on the same line → kept
        self.assertEqual(html.count("[...]"), 1)
        self.assertIn("was arrested", html)

    def test_build_document_html_removal_mode_separate_inline_redactions(self):
        """Two non-adjacent inline redactions in a sentence both produce [...] markers."""
        self.document.extracted_text = "John went to London yesterday."
        self.document.save()
        Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="John",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        Redaction.objects.create(
            document=self.document,
            start_char=13,
            end_char=19,
            text="London",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        html, _ = _build_document_html(self.document, mode="removal")
        # Both redactions are inline within the same sentence → both markers kept
        self.assertEqual(html.count("[...]"), 2)

    def test_cell_fully_redacted_true(self):
        """A cell whose entire non-whitespace content is covered returns True."""
        text = "John Smith"
        r1 = SimpleNamespace(start_char=0, end_char=4)
        r2 = SimpleNamespace(start_char=5, end_char=10)
        self.assertTrue(_cell_fully_redacted(text, 0, len(text), [r1, r2]))

    def test_cell_fully_redacted_false(self):
        """A cell with unredacted non-whitespace content returns False."""
        text = "John went home"
        r = SimpleNamespace(start_char=0, end_char=4)
        self.assertFalse(_cell_fully_redacted(text, 0, len(text), [r]))

    def test_render_table_removal_all_redacted_suppressed(self):
        """A fully-redacted table in removal mode returns empty string."""
        text = "Name\tDOB\n"
        table_data = {
            "ner_start": 0,
            "ner_end": len(text),
            "cells": [
                {"row": 0, "col": 0, "text": "Name", "start": 0, "end": 4},
                {"row": 0, "col": 1, "text": "DOB", "start": 5, "end": 8},
            ],
        }
        redactions = [
            SimpleNamespace(start_char=0, end_char=4),
            SimpleNamespace(start_char=5, end_char=8),
        ]
        result = _render_table_with_redactions(
            table_data, text, redactions, "removal"
        )
        self.assertEqual(result, "")

    def test_render_table_removal_partial_redaction_keeps_table(self):
        """A partially-redacted table in removal mode keeps the table structure."""
        text = "Name\tDOB\n"
        table_data = {
            "ner_start": 0,
            "ner_end": len(text),
            "cells": [
                {"row": 0, "col": 0, "text": "Name", "start": 0, "end": 4},
                {"row": 0, "col": 1, "text": "DOB", "start": 5, "end": 8},
            ],
        }
        redactions = [SimpleNamespace(start_char=0, end_char=4)]
        result = _render_table_with_redactions(
            table_data, text, redactions, "removal"
        )
        self.assertIn("<table", result)

    def test_render_table_removal_mixed_rows_collapses_redacted_rows(self):
        """Fully-redacted rows collapse to a single [...] cell; partial rows render normally."""
        # Row 0: col0="Name" (redacted), col1="Notes" (not redacted)
        # Row 1: col0="John" (redacted), col1="Smith" (redacted) — should collapse
        text = "Name\tNotes\nJohn\tSmith\n"
        table_data = {
            "ner_start": 0,
            "ner_end": len(text),
            "cells": [
                {"row": 0, "col": 0, "text": "Name", "start": 0, "end": 4},
                {"row": 0, "col": 1, "text": "Notes", "start": 5, "end": 10},
                {"row": 1, "col": 0, "text": "John", "start": 11, "end": 15},
                {"row": 1, "col": 1, "text": "Smith", "start": 16, "end": 21},
            ],
        }
        redactions = [
            SimpleNamespace(start_char=0, end_char=4),  # "Name"
            SimpleNamespace(start_char=11, end_char=15),  # "John"
            SimpleNamespace(start_char=16, end_char=21),  # "Smith"
        ]
        result = _render_table_with_redactions(
            table_data, text, redactions, "removal"
        )
        self.assertIn("<table", result)
        # Row 0: col 0 redacted → [...], col 1 unredacted → text
        # Row 1: all redacted, prev row not all-redacted → first cell [...], second cell empty
        self.assertNotIn("colspan=", result)
        self.assertEqual(result.count("[...]"), 2)

    def test_render_table_removal_cell_run_first_gets_marker_rest_empty(self):
        """In a row with consecutive redacted cells, only the first gets [...]; the rest are empty."""
        text = "John\tSmith\tDOB\n"
        table_data = {
            "ner_start": 0,
            "ner_end": len(text),
            "cells": [
                {"row": 0, "col": 0, "text": "John", "start": 0, "end": 4},
                {"row": 0, "col": 1, "text": "Smith", "start": 5, "end": 10},
                {"row": 0, "col": 2, "text": "DOB", "start": 11, "end": 14},
            ],
        }
        redactions = [
            SimpleNamespace(start_char=0, end_char=4),
            SimpleNamespace(start_char=5, end_char=10),
        ]
        result = _render_table_with_redactions(
            table_data, text, redactions, "removal"
        )
        self.assertIn("<table", result)
        self.assertEqual(result.count("[...]"), 1)
        self.assertIn("DOB", result)

    def test_render_table_removal_all_rows_redacted_suppressed(self):
        """A table where every row is fully redacted returns empty string."""
        text = "John\tSmith\nJane\tDoe\n"
        table_data = {
            "ner_start": 0,
            "ner_end": len(text),
            "cells": [
                {"row": 0, "col": 0, "text": "John", "start": 0, "end": 4},
                {"row": 0, "col": 1, "text": "Smith", "start": 5, "end": 10},
                {"row": 1, "col": 0, "text": "Jane", "start": 11, "end": 15},
                {"row": 1, "col": 1, "text": "Doe", "start": 16, "end": 19},
            ],
        }
        redactions = [
            SimpleNamespace(start_char=0, end_char=4),
            SimpleNamespace(start_char=5, end_char=10),
            SimpleNamespace(start_char=11, end_char=15),
            SimpleNamespace(start_char=16, end_char=19),
        ]
        result = _render_table_with_redactions(
            table_data, text, redactions, "removal"
        )
        self.assertEqual(result, "")

    def test_render_table_removal_partial_table_first_redacted_row_shows_marker(
        self,
    ):
        """In a mixed table, the first all-redacted row shows [...] in col 0; a second
        consecutive all-redacted row is skipped."""
        text = "John\tSmith\nJane\tDoe\nNotes\n"
        table_data = {
            "ner_start": 0,
            "ner_end": len(text),
            "cells": [
                {"row": 0, "col": 0, "text": "John", "start": 0, "end": 4},
                {"row": 0, "col": 1, "text": "Smith", "start": 5, "end": 10},
                {"row": 1, "col": 0, "text": "Jane", "start": 11, "end": 15},
                {"row": 1, "col": 1, "text": "Doe", "start": 16, "end": 19},
                {"row": 2, "col": 0, "text": "Notes", "start": 20, "end": 25},
                {"row": 2, "col": 1, "text": "", "start": 25, "end": 25},
            ],
        }
        # Only rows 0 and 1 are redacted; row 2 has unredacted content
        redactions = [
            SimpleNamespace(start_char=0, end_char=4),
            SimpleNamespace(start_char=5, end_char=10),
            SimpleNamespace(start_char=11, end_char=15),
            SimpleNamespace(start_char=16, end_char=19),
        ]
        result = _render_table_with_redactions(
            table_data, text, redactions, "removal"
        )
        self.assertIn("<table", result)
        # Two consecutive all-redacted rows → only one [...] emitted for the first
        self.assertEqual(result.count("[...]"), 1)
        self.assertIn("Notes", result)

    @patch("cases.services._generate_pdf_from_document")
    def test_export_uses_removal_mode_when_configured(self, mock_generate_pdf):
        """When disclosure_style is 'removal', the disclosure PDF uses removal mode."""
        mock_generate_pdf.return_value = b"mock pdf content"
        settings = DocumentExportSettings.get()
        settings.disclosure_style = (
            DocumentExportSettings.DisclosureStyle.REMOVAL
        )
        settings.save()

        export_case_documents(self.case.id)

        calls = mock_generate_pdf.call_args_list
        disclosure_calls = [
            c for c in calls if c.kwargs.get("mode") == "removal"
        ]
        self.assertTrue(len(disclosure_calls) >= 1)

        self.case.refresh_from_db()
        if self.case.export_file:
            import os

            if os.path.exists(self.case.export_file.path):
                os.remove(self.case.export_file.path)

    def test_build_document_html_no_text_returns_none(self):
        """Returns (None, None) when the document has no extracted text."""
        self.document.extracted_text = ""
        self.document.save()
        html, css = _build_document_html(self.document)
        self.assertIsNone(html)
        self.assertIsNone(css)

    def test_build_document_html_custom_font_in_css(self):
        """A non-default font family should appear in the body style."""
        self.document.extracted_text = "Some text for font testing."
        self.document.save()
        export_settings = DocumentExportSettings.get()
        export_settings.font_family = (
            DocumentExportSettings.FontFamily.TIMES_NEW_ROMAN
        )
        export_settings.save()

        html, _ = _build_document_html(
            self.document, mode="disclosure", export_settings=export_settings
        )
        self.assertIsNotNone(html)
        self.assertIn("Times New Roman", html)

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
                self.document.original_file.name
            )
            self.assertIn(
                f"unedited/{original_file_basename}",
                filenames,
            )
            self.assertIn(
                f"unedited/{os.path.basename(doc2.original_file.name)}",
                filenames,
            )
            # Check for redacted PDFs
            self.assertIn("redacted/document.pdf", filenames)
            self.assertIn("redacted/doc2.pdf", filenames)
            # Check for disclosure PDFs
            self.assertIn("disclosure/document.pdf", filenames)
            self.assertIn("disclosure/doc2.pdf", filenames)

        # Check that the PDF generator was called for each document and mode
        self.assertEqual(mock_generate_pdf.call_count, 4)  # 2 docs * 2 modes

        # Clean up the created export file
        if os.path.exists(zip_path):
            os.remove(zip_path)

    @patch("cases.services._generate_pdf_from_document")
    def test_export_deduplicates_colliding_filenames(self, mock_generate_pdf):
        """Documents sharing a filename must not overwrite each other in the ZIP."""
        mock_generate_pdf.return_value = b"mock pdf content"

        clash1 = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("report.txt", b"one"),
            extracted_text="Some text",
        )
        clash2 = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("report.txt", b"two"),
            extracted_text="Other text",
        )
        # Force identical stored filenames regardless of storage suffixing
        Document.objects.filter(pk__in=[clash1.pk, clash2.pk]).update(
            filename="report.txt"
        )

        export_case_documents(self.case.id)

        self.case.refresh_from_db()
        self.assertEqual(self.case.export_status, Case.ExportStatus.COMPLETED)
        zip_path = self.case.export_file.path
        with zipfile.ZipFile(zip_path, "r") as zf:
            filenames = zf.namelist()
            self.assertIn("redacted/report.pdf", filenames)
            self.assertIn("redacted/report_1.pdf", filenames)
            self.assertIn("disclosure/report.pdf", filenames)
            self.assertIn("disclosure/report_1.pdf", filenames)

        if os.path.exists(zip_path):
            os.remove(zip_path)

    def test_export_case_not_found(self):
        """Test that the export function handles a non-existent case ID."""
        non_existent_id = uuid.uuid4()
        export_case_documents(non_existent_id)
        self.assertFalse(Case.objects.filter(id=non_existent_id).exists())

    @patch("cases.services.extract_entities_from_text")
    @patch("cases.services.SpanCatModelManager")
    @patch("cases.services.GLiNERModelManager")
    def test_process_document_filters_data_subject_entities(
        self, mock_gliner_manager, mock_spancat_manager, mock_extract_entities
    ):
        """Test that entities matching the data subject name/DOB are excluded."""
        mock_gliner_manager.get_instance.return_value = MagicMock()
        mock_spancat_manager.get_instance.return_value = MagicMock(
            get_model_entry=MagicMock(return_value=None)
        )

        extracted_text = "John Doe lives in London. DOB: 01/01/1990."
        suggestions = [
            {
                "start_char": 0,
                "end_char": 8,
                "text": "John Doe",
                "label": "THIRD_PARTY",
            },
            {
                "start_char": 18,
                "end_char": 24,
                "text": "London",
                "label": "THIRD_PARTY",
            },
            {
                "start_char": 31,
                "end_char": 41,
                "text": "01/01/1990",
                "label": "THIRD_PARTY",
            },
        ]
        mock_extract_entities.return_value = (
            extracted_text,
            suggestions,
            [],
            None,
        )

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
            retention_review_date=timezone.now().date()
            + relativedelta(days=1),
        )

        with patch("cases.services.logger") as mock_logger:
            result = delete_cases_past_retention_date()
            self.assertEqual(result, "No cases are due for deletion.")
            self.assertEqual(Case.objects.count(), 1)
            mock_logger.info.assert_called_with(
                "No cases are due for deletion."
            )

    def test_deletes_case_past_retention_date(self):
        """
        Test that a single case past its retention date is correctly deleted,
        along with its associated files.
        """
        past_date = timezone.now().date() - relativedelta(days=1)
        case_to_delete = Case.objects.create(
            case_reference="PAST01",
            data_subject_name="Past Person",
            retention_review_date=past_date,
        )

        doc_file = SimpleUploadedFile("test_doc.txt", b"some content")
        doc = Document.objects.create(
            case=case_to_delete, original_file=doc_file
        )
        self.assertTrue(os.path.exists(doc.original_file.path))

        export_file = SimpleUploadedFile("export.zip", b"zip content")
        case_to_delete.export_file.save(export_file.name, export_file)
        self.assertTrue(os.path.exists(case_to_delete.export_file.path))

        Case.objects.create(
            case_reference="FUTR02",
            data_subject_name="Future Person 2",
            retention_review_date=timezone.now().date()
            + relativedelta(days=10),
        )

        self.assertEqual(Case.objects.count(), 2)
        self.assertEqual(Document.objects.count(), 1)

        with patch("cases.services.logger") as mock_logger:
            result = delete_cases_past_retention_date()
            self.assertEqual(result, "Successfully deleted 1 case(s): PAST01.")
            mock_logger.info.assert_has_calls(
                [
                    call("Found 1 case(s) due for deletion."),
                    call(
                        f"Deleting case PAST01 (Retention Date: {past_date})"
                    ),
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
        css = _build_export_css(
            self._make_settings(footer_text="Confidential")
        )
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
        css = _build_export_css(
            self._make_settings(
                footer_text="Confidential", page_numbers_enabled=True
            )
        )
        self.assertIn("@bottom-center", css)
        self.assertIn("Confidential", css)
        self.assertIn("counter(page)", css)
        self.assertIn(r"\A", css)

    def test_watermark_css_emitted_when_watermark_text_set(self):
        css = _build_export_css(
            self._make_settings(
                watermark_text="SAR", watermark_include_case_ref=True
            ),
            case_reference="2025-001",
        )
        self.assertIn(".watermark", css)
        self.assertIn("rotate(-45deg)", css)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class GeneratePdfWithSettingsTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="CSS01", data_subject_name="Test User"
        )
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
        result = _generate_pdf_from_document(
            self.document, mode="disclosure", export_settings=settings
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result[:4] == b"%PDF")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ExportCaseDocumentsPassesSettingsTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="EXP01", data_subject_name="Export User"
        )
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
            patch(
                "cases.services.DocumentExportSettings.get",
                return_value=mock_settings,
            ) as mock_get,
            patch(
                "cases.services._generate_pdf_from_document",
                return_value=b"%PDF-test",
            ) as mock_gen,
        ):
            export_case_documents(self.case.id)

        mock_get.assert_called_once()
        calls = mock_gen.call_args_list
        self.assertEqual(len(calls), 2)
        for c in calls:
            self.assertEqual(c.kwargs["export_settings"], mock_settings)
            self.assertEqual(c.kwargs["case_reference"], "EXP01")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ExportPreservationTests(NetworkBlockerMixin, TestCase):
    """Every disclosure is preserved as its own Export + linked snapshot."""

    def setUp(self):
        self.case = Case.objects.create(
            case_reference="250099", data_subject_name="Jane Roe"
        )
        self.document = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("doc.txt", b"Some text"),
            extracted_text="Some operational text here",
            status=Document.Status.COMPLETED,
        )
        self.redaction = Redaction.objects.create(
            document=self.document,
            start_char=5,
            end_char=16,
            text="operational",
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        RedactionContext.objects.create(
            redaction=self.redaction, text="Some operational text"
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    @patch(
        "cases.services._generate_pdf_from_document",
        return_value=b"mock pdf content",
    )
    def test_export_creates_export_and_linked_snapshot(self, _mock_pdf):
        export_case_documents(self.case.id)

        exports = self.case.exports.all()
        self.assertEqual(exports.count(), 1)
        export = exports.first()
        self.assertEqual(export.sequence, 1)
        self.assertEqual(export.label, "Original disclosure")
        self.assertTrue(export.export_file.name.endswith(".zip"))
        self.assertIsNone(export.review)

        # The snapshot is frozen and tied to this export.
        snapshot = export.snapshot
        self.assertIsInstance(snapshot, RedactionSnapshot)
        self.assertEqual(snapshot.case_id, self.case.id)
        self.assertEqual(len(snapshot.payload), 1)
        self.assertEqual(snapshot.payload[0]["id"], str(self.redaction.id))

        # Case.export_file points at the new export's stored file.
        self.case.refresh_from_db()
        self.assertEqual(self.case.export_status, Case.ExportStatus.COMPLETED)
        self.assertEqual(self.case.export_file.name, export.export_file.name)

    @patch(
        "cases.services._generate_pdf_from_document",
        return_value=b"mock pdf content",
    )
    def test_re_export_preserves_prior_export(self, _mock_pdf):
        export_case_documents(self.case.id)
        first = self.case.exports.get(sequence=1)
        first_file = first.export_file.name

        export_case_documents(self.case.id)

        exports = list(self.case.exports.order_by("sequence"))
        self.assertEqual(len(exports), 2)
        self.assertEqual([e.sequence for e in exports], [1, 2])
        self.assertEqual(
            [e.label for e in exports],
            ["Original disclosure", "Disclosure 2"],
        )
        # First export is untouched; the two files are distinct.
        first.refresh_from_db()
        self.assertEqual(first.export_file.name, first_file)
        self.assertNotEqual(exports[1].export_file.name, first_file)
        self.assertTrue(os.path.exists(first.export_file.path))
        self.assertTrue(os.path.exists(exports[1].export_file.path))

        # Each export carries its own snapshot.
        self.assertTrue(all(e.snapshot is not None for e in exports))

        # Case pointer follows the latest export.
        self.case.refresh_from_db()
        self.assertEqual(
            self.case.export_file.name, exports[1].export_file.name
        )

    @patch(
        "cases.services._generate_pdf_from_document",
        return_value=b"mock pdf content",
    )
    def test_export_attributes_package_to_review(self, _mock_pdf):
        """A completion-triggered re-export links its Export to the review."""
        export_case_documents(self.case.id)
        review = InternalReview.objects.create(
            case=self.case, status=InternalReview.Status.COMPLETED
        )

        export_case_documents(self.case.id, review_id=str(review.id))

        latest = self.case.exports.order_by("-sequence").first()
        self.assertEqual(latest.review_id, review.id)


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
        result = _render_table_with_redactions(
            {"text": "plain <text>"}, "", [], "internal"
        )
        self.assertEqual(result, "plain &lt;text&gt;")

    def test_no_cells_empty_text_returns_empty_string(self):
        result = _render_table_with_redactions({}, "", [], "internal")
        self.assertEqual(result, "")

    def test_simple_table_structure(self):
        full_text = "Hello World"
        table_data = {
            "cells": [
                self._cell(
                    0,
                    0,
                    0,
                    5,
                    "Hello",
                    isMergedContinuation=False,
                    colspan=1,
                    rowspan=1,
                ),
                self._cell(
                    0,
                    1,
                    6,
                    11,
                    "World",
                    isMergedContinuation=False,
                    colspan=1,
                    rowspan=1,
                ),
            ]
        }
        result = _render_table_with_redactions(
            table_data, full_text, [], "internal"
        )
        self.assertIn("<table", result)
        self.assertIn("<tr>", result)
        self.assertIn("Hello", result)
        self.assertIn("World", result)

    def test_redaction_applied_within_cell(self):
        full_text = "Hello World"
        table_data = {
            "cells": [
                self._cell(
                    0,
                    0,
                    0,
                    5,
                    "Hello",
                    isMergedContinuation=False,
                    colspan=1,
                    rowspan=1,
                ),
                self._cell(
                    0,
                    1,
                    6,
                    11,
                    "World",
                    isMergedContinuation=False,
                    colspan=1,
                    rowspan=1,
                ),
            ]
        }
        redaction = _make_redaction(6, 11)
        result = _render_table_with_redactions(
            table_data, full_text, [redaction], "internal"
        )
        self.assertIn('class="redaction', result)
        self.assertIn("World", result)

    def test_disclosure_mode_replaces_with_blocks(self):
        full_text = "Secret data"
        table_data = {
            "cells": [
                self._cell(
                    0,
                    0,
                    0,
                    6,
                    "Secret",
                    isMergedContinuation=False,
                    colspan=1,
                    rowspan=1,
                ),
                self._cell(
                    0,
                    1,
                    7,
                    11,
                    "data",
                    isMergedContinuation=False,
                    colspan=1,
                    rowspan=1,
                ),
            ]
        }
        redaction = _make_redaction(0, 6)
        result = _render_table_with_redactions(
            table_data, full_text, [redaction], "disclosure"
        )
        self.assertIn('class="redaction"', result)
        self.assertNotIn("Secret", result)

    def test_merged_continuation_cell_skipped(self):
        full_text = "MergedMerged"
        table_data = {
            "cells": [
                self._cell(
                    0,
                    0,
                    0,
                    6,
                    "Merged",
                    isMergedContinuation=False,
                    colspan=2,
                    rowspan=1,
                ),
                self._cell(
                    0,
                    1,
                    0,
                    6,
                    "Merged",
                    isMergedContinuation=True,
                    colspan=1,
                    rowspan=1,
                ),
            ]
        }
        result = _render_table_with_redactions(
            table_data, full_text, [], "internal"
        )
        # Only one <td> should be rendered (the continuation is skipped)
        self.assertEqual(result.count("<td"), 1)
        self.assertIn('colspan="2"', result)

    def test_colspan_and_rowspan_attrs_rendered(self):
        full_text = "AB"
        table_data = {
            "cells": [
                self._cell(
                    0,
                    0,
                    0,
                    1,
                    "A",
                    isMergedContinuation=False,
                    colspan=3,
                    rowspan=2,
                ),
            ]
        }
        result = _render_table_with_redactions(
            table_data, full_text, [], "internal"
        )
        self.assertIn('colspan="3"', result)
        self.assertIn('rowspan="2"', result)

    def test_col_widths_applied(self):
        full_text = "AB"
        table_data = {
            "cells": [
                self._cell(
                    0,
                    0,
                    0,
                    1,
                    "A",
                    isMergedContinuation=False,
                    colspan=1,
                    rowspan=1,
                )
            ],
            "colWidths": [42.5],
        }
        result = _render_table_with_redactions(
            table_data, full_text, [], "internal"
        )
        self.assertIn("width: 42.5%", result)

    def test_equal_fallback_widths_when_no_col_widths(self):
        full_text = "AB"
        table_data = {
            "cells": [
                self._cell(
                    0,
                    0,
                    0,
                    1,
                    "A",
                    isMergedContinuation=False,
                    colspan=1,
                    rowspan=1,
                ),
                self._cell(
                    0,
                    1,
                    1,
                    2,
                    "B",
                    isMergedContinuation=False,
                    colspan=1,
                    rowspan=1,
                ),
            ]
        }
        result = _render_table_with_redactions(
            table_data, full_text, [], "internal"
        )
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
        result = _render_table_with_redactions(
            table_data, full_text, [], "internal"
        )
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
        result = _render_table_with_redactions(
            table_data, full_text, [], "internal"
        )
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

    @override_settings(
        DELETE_ORIGINAL_FILES=True, DELETE_ORIGINAL_FILES_AFTER_DAYS=30
    )
    def test_within_threshold_not_deleted(self):
        # Case updated_at is effectively "now" — within 30 days
        result = delete_original_files_past_threshold()
        self.assertEqual(result, "Deleted original files for 0 document(s).")
        self.document.refresh_from_db()
        self.assertTrue(bool(self.document.original_file))

    @override_settings(
        DELETE_ORIGINAL_FILES=True, DELETE_ORIGINAL_FILES_AFTER_DAYS=0
    )
    def test_past_threshold_deletes_original_file(self):
        file_path = self.document.original_file.path
        self.assertTrue(os.path.exists(file_path))
        result = delete_original_files_past_threshold()
        self.assertEqual(result, "Deleted original files for 1 document(s).")
        self.document.refresh_from_db()
        self.assertFalse(bool(self.document.original_file))
        # The file must be removed from storage, not just unlinked in the DB.
        self.assertFalse(os.path.exists(file_path))

    @override_settings(
        DELETE_ORIGINAL_FILES=True, DELETE_ORIGINAL_FILES_AFTER_DAYS=0
    )
    def test_non_terminal_case_not_deleted(self):
        self.case.status = Case.Status.OPEN
        self.case.save()
        result = delete_original_files_past_threshold()
        self.assertEqual(result, "Deleted original files for 0 document(s).")
        self.document.refresh_from_db()
        self.assertTrue(bool(self.document.original_file))


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ApplyExistingCaseDecisionsTests(NetworkBlockerMixin, TestCase):
    """Tests for _apply_existing_case_decisions — prior decision propagation."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="decisionuser", password="pw"
        )
        self.case = Case.objects.create(
            case_reference="DC01",
            data_subject_name="Test Subject",
            created_by=self.user,
        )
        file1 = SimpleUploadedFile("old.pdf", b"x", "application/pdf")
        file2 = SimpleUploadedFile("new.pdf", b"y", "application/pdf")
        self.old_doc = Document.objects.create(
            case=self.case, original_file=file1
        )
        self.new_doc = Document.objects.create(
            case=self.case, original_file=file2
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _pending(self, doc, text, rtype):
        return Redaction.objects.create(
            document=doc,
            start_char=0,
            end_char=len(text),
            text=text,
            redaction_type=rtype,
            is_suggestion=True,
            is_accepted=False,
        )

    def test_propagates_unanimous_accept_to_new_document(self):
        # Existing document has "John Doe" accepted
        r_old = self._pending(
            self.old_doc, "John Doe", Redaction.RedactionType.THIRD_PARTY_PII
        )
        r_old.is_accepted = True
        r_old.decided_by = Redaction.DecidedBy.HUMAN
        r_old.save()

        r_new = self._pending(
            self.new_doc, "John Doe", Redaction.RedactionType.THIRD_PARTY_PII
        )

        _apply_existing_case_decisions(self.new_doc)

        r_new.refresh_from_db()
        self.assertTrue(r_new.is_accepted)
        # The machine decision is recorded as such and must never feed
        # SpanCat training (regression test for the propagation leak).
        self.assertEqual(
            r_new.decided_by, Redaction.DecidedBy.CASE_PROPAGATION
        )
        self.assertTrue(r_new.auto_accepted)
        self.assertNotIn(r_new, Redaction.objects.trainable())

    def test_propagates_unanimous_reject_to_new_document(self):
        r_old = self._pending(
            self.old_doc, "PC Smith", Redaction.RedactionType.OPERATIONAL_DATA
        )
        r_old.is_accepted = False
        r_old.justification = "Not relevant"
        r_old.decided_by = Redaction.DecidedBy.HUMAN
        r_old.save()

        r_new = self._pending(
            self.new_doc, "PC Smith", Redaction.RedactionType.OPERATIONAL_DATA
        )

        _apply_existing_case_decisions(self.new_doc)

        r_new.refresh_from_db()
        self.assertFalse(r_new.is_accepted)
        self.assertEqual(r_new.justification, "Not relevant")
        self.assertEqual(
            r_new.decided_by, Redaction.DecidedBy.CASE_PROPAGATION
        )

    def test_mixed_decisions_leave_new_redaction_pending(self):
        r1 = self._pending(
            self.old_doc, "Jane Doe", Redaction.RedactionType.THIRD_PARTY_PII
        )
        r1.is_accepted = True
        r1.decided_by = Redaction.DecidedBy.HUMAN
        r1.save()

        file3 = SimpleUploadedFile("mid.pdf", b"z", "application/pdf")
        mid_doc = Document.objects.create(case=self.case, original_file=file3)
        r2 = self._pending(
            mid_doc, "Jane Doe", Redaction.RedactionType.THIRD_PARTY_PII
        )
        r2.justification = "Rejected for different reason"
        r2.decided_by = Redaction.DecidedBy.HUMAN
        r2.save()

        r_new = self._pending(
            self.new_doc, "Jane Doe", Redaction.RedactionType.THIRD_PARTY_PII
        )

        _apply_existing_case_decisions(self.new_doc)

        r_new.refresh_from_db()
        self.assertFalse(r_new.is_accepted)
        self.assertFalse(r_new.justification)

    def test_no_existing_decisions_leaves_pending(self):
        r_new = self._pending(
            self.new_doc, "Unknown", Redaction.RedactionType.THIRD_PARTY_PII
        )

        _apply_existing_case_decisions(self.new_doc)

        r_new.refresh_from_db()
        self.assertFalse(r_new.is_accepted)
        self.assertIsNone(r_new.justification)

    def test_decisions_from_other_cases_do_not_propagate(self):
        other_case = Case.objects.create(
            case_reference="DC02",
            data_subject_name="Other",
            created_by=self.user,
        )
        other_file = SimpleUploadedFile("other.pdf", b"w", "application/pdf")
        other_doc = Document.objects.create(
            case=other_case, original_file=other_file
        )
        r_other = self._pending(
            other_doc, "John Doe", Redaction.RedactionType.THIRD_PARTY_PII
        )
        r_other.is_accepted = True
        r_other.decided_by = Redaction.DecidedBy.HUMAN
        r_other.save()

        r_new = self._pending(
            self.new_doc, "John Doe", Redaction.RedactionType.THIRD_PARTY_PII
        )

        _apply_existing_case_decisions(self.new_doc)

        r_new.refresh_from_db()
        self.assertFalse(r_new.is_accepted)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ApplyCaseDsInfoToDocumentTests(NetworkBlockerMixin, TestCase):
    """Tests for _apply_case_ds_info_to_document — DS_INFO propagation on upload."""

    def setUp(self):
        self.case = Case.objects.create(
            case_reference="DS01",
            data_subject_name="Test Subject",
        )
        file1 = SimpleUploadedFile("existing.pdf", b"x", "application/pdf")
        file2 = SimpleUploadedFile("new.pdf", b"y", "application/pdf")
        self.existing_doc = Document.objects.create(
            case=self.case,
            original_file=file1,
            status=Document.Status.READY_FOR_REVIEW,
        )
        self.new_doc = Document.objects.create(
            case=self.case,
            original_file=file2,
            status=Document.Status.READY_FOR_REVIEW,
            extracted_text="Alice spoke to the officer about the party.",
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _ds_info(self, doc, text, accepted=True):
        return Redaction.objects.create(
            document=doc,
            start_char=0,
            end_char=len(text),
            text=text,
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
            is_accepted=accepted,
            decided_by=Redaction.DecidedBy.HUMAN if accepted else None,
        )

    def test_creates_accepted_ds_info_for_matching_text(self):
        self._ds_info(self.existing_doc, "Alice")

        _apply_case_ds_info_to_document(self.new_doc)

        redactions = self.new_doc.redactions.all()
        self.assertEqual(redactions.count(), 1)
        r = redactions.first()
        self.assertEqual(r.text, "Alice")
        self.assertEqual(
            r.redaction_type, Redaction.RedactionType.DS_INFORMATION
        )
        self.assertTrue(r.is_accepted)

    def test_does_not_create_redactions_when_no_case_ds_info(self):
        _apply_case_ds_info_to_document(self.new_doc)

        self.assertEqual(self.new_doc.redactions.count(), 0)

    def test_ignores_unaccepted_ds_info_from_other_documents(self):
        self._ds_info(self.existing_doc, "Alice", accepted=False)

        _apply_case_ds_info_to_document(self.new_doc)

        self.assertEqual(self.new_doc.redactions.count(), 0)

    def test_does_nothing_when_document_has_no_extracted_text(self):
        self.new_doc.extracted_text = None
        self.new_doc.save(update_fields=["extracted_text"])
        self._ds_info(self.existing_doc, "Alice")

        _apply_case_ds_info_to_document(self.new_doc)

        self.assertEqual(self.new_doc.redactions.count(), 0)
