import os
import shutil
import tempfile
import uuid
from datetime import date
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, override_settings
from freezegun import freeze_time

from cases.models import (
    Case,
    DisclosureLockError,
    Document,
    DocumentExportSettings,
    Export,
    InternalReview,
    ProvenanceError,
    Redaction,
    RedactionContext,
)
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
            case_reference="202501", data_subject_name="Alice Example"
        )
        self.assertIn("Case 202501 - Alice Example", str(case))

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_case_creation_with_user(self):
        user = User.objects.create_user(
            username="testuser", password="password"
        )
        case = Case.objects.create(
            case_reference="20251A",
            data_subject_name="User Test",
            created_by=user,
        )
        self.assertEqual(case.created_by, user)
        self.assertEqual(case.created_by.username, "testuser")

    @freeze_time("2025-09-27")
    def test_retention_review_date_for_adult(self):
        # Test that the save() method correctly sets the date on creation
        dob = date(2005, 9, 27)  # 20 years old
        case = Case.objects.create(
            case_reference="202502",
            data_subject_name="Adult Example",
            data_subject_dob=dob,
        )
        expected = date(2031, 9, 27)  # 2025 + 6 years
        self.assertEqual(case.retention_review_date, expected)

    def test_calculate_retention_date_for_adult_direct(self):
        fixed_today = date(2025, 9, 27)
        dob = fixed_today - relativedelta(years=25)
        case = Case(
            case_reference="20252A",
            data_subject_name="Adult Direct",
            data_subject_dob=dob,
        )
        case.retention_review_date = case._calculate_retention_date(
            today=fixed_today
        )
        expected = fixed_today + relativedelta(years=6)
        self.assertEqual(case.retention_review_date, expected)

    def test_retention_review_date_for_minor(self):
        fixed_today = date(2024, 9, 27)
        dob = date(2015, 9, 27)
        case = Case(
            case_reference="202503",
            data_subject_name="Minor Example",
            data_subject_dob=dob,
        )
        # With today as 2024-09-27, the subject is 9.
        # The rule for minors applies.
        # 18th birthday is 2033-09-27. Retention is 6 years after: 2039-09-27.
        calculated_date = case._calculate_retention_date(today=fixed_today)
        self.assertEqual(calculated_date, date(2039, 9, 27))

    @freeze_time("2024-09-27")
    def test_retention_review_date_for_minor_applied_on_save(self):
        # Regression: save() must apply the minor rule on creation. The old
        # `if not self.pk` check never fired because UUID pks are assigned
        # at instantiation, leaving the flat 6-year field default in place.
        case = Case.objects.create(
            case_reference="20253C",
            data_subject_name="Minor Saved",
            data_subject_dob=date(2015, 9, 27),
        )
        case.refresh_from_db()
        # 18th birthday is 2033-09-27; retention is 6 years after.
        self.assertEqual(case.retention_review_date, date(2039, 9, 27))

    def test_retention_review_date_for_eighteen_year_old(self):
        # Test edge case: someone who is exactly 18
        fixed_today = date(2025, 9, 27)
        dob = fixed_today - relativedelta(years=18)  # DOB is 2007-09-27
        case = Case(
            case_reference="20253B",
            data_subject_name="18yo",
            data_subject_dob=dob,
        )
        # For someone who is exactly 18, the rule is still 6 years from today.
        calculated_date = case._calculate_retention_date(today=fixed_today)
        self.assertEqual(calculated_date, fixed_today + relativedelta(years=6))

    @freeze_time("2025-09-27")
    def test_retention_review_date_no_dob(self):
        # Test that save() correctly sets the date when DOB is not provided
        case = Case.objects.create(
            case_reference="202504", data_subject_name="No DOB"
        )
        expected = date(2031, 9, 27)  # 2025 + 6 years
        self.assertEqual(case.retention_review_date, expected)

    def test_case_status_default(self):
        case = Case.objects.create(
            case_reference="202505", data_subject_name="Status Default"
        )
        self.assertEqual(case.status, Case.Status.OPEN)

    def test_case_export_status_default(self):
        case = Case.objects.create(
            case_reference="202506", data_subject_name="Export Status Default"
        )
        self.assertEqual(case.export_status, Case.ExportStatus.NONE)

    @patch("cases.models.async_task")
    def test_start_export_method(self, mock_async_task):
        """Test the start_export method on the Case model."""
        mock_async_task.return_value = "model-test-task-id"
        case = Case.objects.create(
            case_reference="202507", data_subject_name="Export Method Test"
        )
        self.assertEqual(case.export_status, Case.ExportStatus.NONE)

        task_id = case.start_export()

        self.assertEqual(task_id, "model-test-task-id")
        mock_async_task.assert_called_once_with(
            "cases.tasks.export_case_documents", case.id, None
        )
        self.assertEqual(case.export_status, Case.ExportStatus.PROCESSING)
        self.assertEqual(case.export_task_id, "model-test-task-id")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class DocumentModelTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="202510", data_subject_name="Doc Test"
        )
        self.model = Model.objects.create(name="Test Model")

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_document_str(self):
        file = SimpleUploadedFile("test.pdf", b"file_content")
        doc = Document.objects.create(
            case=self.case, original_file=file, spacy_model=self.model
        )
        self.assertEqual(
            "test.pdf", return_test_file_name(doc.original_file.name)
        )

    def test_document_filename_and_filetype(self):
        file = SimpleUploadedFile("sample.docx", b"file_content")
        doc = Document.objects.create(case=self.case, original_file=file)
        self.assertEqual(
            return_test_file_name(doc.original_file.name), "sample.docx"
        )
        self.assertIn(".docx", doc.original_file.name)

    def test_document_filename_and_filetype_on_save(self):
        file = SimpleUploadedFile("report.pdf", b"file_content")
        doc = Document.objects.create(case=self.case, original_file=file)
        self.assertEqual(
            return_test_file_name(doc.original_file.name), "report.pdf"
        )
        self.assertIn(".pdf", return_test_file_name(doc.original_file.name))

    def test_document_model_save_sets_serializer_format_file_type(self):
        """Model-level creation must match DocumentSerializer's file_type
        format (extension with leading dot), which the frontend matches on."""
        file = SimpleUploadedFile("occurrence.pdf", b"file_content")
        doc = Document.objects.create(case=self.case, original_file=file)
        self.assertEqual(doc.filename, "occurrence.pdf")
        self.assertEqual(doc.file_type, ".pdf")

    def test_document_model_save_preserves_caller_set_fields(self):
        file = SimpleUploadedFile("raw-upload.pdf", b"file_content")
        doc = Document.objects.create(
            case=self.case,
            original_file=file,
            filename="Friendly name.pdf",
            file_type=".pdf",
        )
        self.assertEqual(doc.filename, "Friendly name.pdf")
        self.assertEqual(doc.file_type, ".pdf")

    def test_document_status_default(self):
        file = SimpleUploadedFile("default.txt", b"file_content")
        doc = Document.objects.create(case=self.case, original_file=file)
        self.assertEqual(doc.status, Document.Status.PROCESSING)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RedactionModelTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="202520", data_subject_name="Redaction Test"
        )
        file = SimpleUploadedFile("redact.txt", b"file_content")
        self.document = Document.objects.create(
            case=self.case, original_file=file
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_redaction_str(self):
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=10,
            text="Sensitive Data",
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
        )
        self.assertIn("Sensitive Data", str(redaction))

    def test_redaction_with_justification(self):
        justification_text = (
            "This is a manual redaction for a specific reason."
        )
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=10,
            text="Secret Info",
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
            is_suggestion=False,
            is_accepted=True,
            justification=justification_text,
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        self.assertEqual(redaction.justification, justification_text)

    def test_redaction_defaults(self):
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=5,
            end_char=15,
            text="PII Example",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        self.assertTrue(redaction.is_suggestion)
        self.assertFalse(redaction.is_accepted)

    def test_source_defaults_to_ner(self):
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=5,
            text="Alice",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        self.assertEqual(redaction.source, Redaction.Source.NER)

    def test_source_can_be_set_to_llm(self):
        redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=5,
            text="Alice",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            source=Redaction.Source.LLM,
        )
        self.assertEqual(redaction.source, Redaction.Source.LLM)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RedactionQuerySetDecisionTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="202540", data_subject_name="QS Decision Test"
        )
        file = SimpleUploadedFile("qs.txt", b"content")
        self.document = Document.objects.create(
            case=self.case, original_file=file
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _make_redaction(self, **kwargs):
        defaults = {
            "document": self.document,
            "start_char": 0,
            "end_char": 4,
            "text": "test",
            "redaction_type": Redaction.RedactionType.THIRD_PARTY_PII,
        }
        defaults.update(kwargs)
        return Redaction.objects.create(**defaults)

    def test_accept_sets_is_accepted_and_provenance(self):
        r = self._make_redaction()
        Redaction.objects.filter(pk=r.pk).accept(by=Redaction.DecidedBy.HUMAN)
        r.refresh_from_db()
        self.assertTrue(r.is_accepted)
        self.assertEqual(r.decided_by, Redaction.DecidedBy.HUMAN)
        self.assertFalse(r.auto_accepted)

    def test_accept_records_each_machine_mechanism(self):
        for mechanism in (
            Redaction.DecidedBy.AUTO_ACCEPT,
            Redaction.DecidedBy.CASE_PROPAGATION,
            Redaction.DecidedBy.DS_INFO_PROPAGATION,
        ):
            with self.subTest(mechanism=mechanism):
                r = self._make_redaction()
                Redaction.objects.filter(pk=r.pk).accept(by=mechanism)
                r.refresh_from_db()
                self.assertTrue(r.is_accepted)
                self.assertEqual(r.decided_by, mechanism)
                self.assertTrue(r.auto_accepted)

    def test_accept_without_by_raises_type_error(self):
        r = self._make_redaction()
        with self.assertRaises(TypeError):
            Redaction.objects.filter(pk=r.pk).accept()

    def test_reject_without_by_raises_type_error(self):
        r = self._make_redaction()
        with self.assertRaises(TypeError):
            Redaction.objects.filter(pk=r.pk).reject("reason")

    def test_accept_clears_stale_rejection_justification(self):
        r = self._make_redaction(
            justification="old rejection reason",
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        Redaction.objects.filter(pk=r.pk).accept(by=Redaction.DecidedBy.HUMAN)
        r.refresh_from_db()
        self.assertTrue(r.is_accepted)
        self.assertIsNone(r.justification)

    def test_reject_sets_is_accepted_false_and_justification(self):
        r = self._make_redaction(
            is_accepted=True, decided_by=Redaction.DecidedBy.HUMAN
        )
        Redaction.objects.filter(pk=r.pk).reject(
            "S.40 - Personal Information", by=Redaction.DecidedBy.HUMAN
        )
        r.refresh_from_db()
        self.assertFalse(r.is_accepted)
        self.assertEqual(r.justification, "S.40 - Personal Information")
        self.assertEqual(r.decided_by, Redaction.DecidedBy.HUMAN)

    def test_reject_with_blank_justification_still_counts_as_decided(self):
        """Provenance makes an unjustified rejection representable."""
        r = self._make_redaction()
        Redaction.objects.filter(pk=r.pk).reject(
            "", by=Redaction.DecidedBy.CASE_PROPAGATION
        )
        r.refresh_from_db()
        self.assertFalse(r.is_accepted)
        self.assertEqual(r.justification, "")
        self.assertNotIn(r, Redaction.objects.pending())
        self.assertIn(r, Redaction.objects.decided())

    def test_reset_returns_to_pending_and_clears_provenance(self):
        r = self._make_redaction(
            is_accepted=True,
            justification="old reason",
            decided_by=Redaction.DecidedBy.HUMAN,
        )
        Redaction.objects.filter(pk=r.pk).reset()
        r.refresh_from_db()
        self.assertFalse(r.is_accepted)
        self.assertIsNone(r.justification)
        self.assertIsNone(r.decided_by)
        self.assertIn(r, Redaction.objects.pending())

    def test_accept_moves_out_of_pending(self):
        r = self._make_redaction()
        self.assertIn(r, Redaction.objects.pending())
        Redaction.objects.filter(pk=r.pk).accept(by=Redaction.DecidedBy.HUMAN)
        self.assertNotIn(r, Redaction.objects.pending())
        self.assertIn(r, Redaction.objects.decided())

    def test_accept_returns_count(self):
        self._make_redaction()
        self._make_redaction(start_char=5, end_char=9)
        count = Redaction.objects.all().accept(by=Redaction.DecidedBy.HUMAN)
        self.assertEqual(count, 2)

    def test_reject_returns_count(self):
        self._make_redaction()
        count = Redaction.objects.all().reject(
            "reason", by=Redaction.DecidedBy.HUMAN
        )
        self.assertEqual(count, 1)

    def test_update_of_decision_fields_raises_provenance_error(self):
        self._make_redaction()
        for kwargs in (
            {"is_accepted": True},
            {"justification": "reason"},
            {"decided_by": Redaction.DecidedBy.HUMAN},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ProvenanceError):
                    Redaction.objects.all().update(**kwargs)

    def test_update_of_non_decision_fields_still_allowed(self):
        r = self._make_redaction()
        Redaction.objects.filter(pk=r.pk).update(
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA
        )
        r.refresh_from_db()
        self.assertEqual(
            r.redaction_type, Redaction.RedactionType.OPERATIONAL_DATA
        )

    def test_bulk_update_of_decision_fields_raises_provenance_error(self):
        r = self._make_redaction()
        r.is_accepted = True
        with self.assertRaises(ProvenanceError):
            Redaction.objects.bulk_update([r], ["is_accepted"])

    def test_bulk_create_accepted_without_provenance_violates_constraint(
        self,
    ):
        with self.assertRaises(IntegrityError):
            Redaction.objects.bulk_create(
                [
                    Redaction(
                        document=self.document,
                        start_char=0,
                        end_char=4,
                        text="test",
                        redaction_type=(
                            Redaction.RedactionType.THIRD_PARTY_PII
                        ),
                        is_accepted=True,
                    )
                ]
            )

    def test_human_accept_overrides_machine_provenance(self):
        r = self._make_redaction(
            is_accepted=True, decided_by=Redaction.DecidedBy.AUTO_ACCEPT
        )
        self.assertNotIn(r, Redaction.objects.trainable())
        Redaction.objects.filter(pk=r.pk).accept(by=Redaction.DecidedBy.HUMAN)
        r.refresh_from_db()
        self.assertEqual(r.decided_by, Redaction.DecidedBy.HUMAN)
        self.assertFalse(r.auto_accepted)
        self.assertIn(r, Redaction.objects.trainable())

    def test_trainable_selects_only_human_accepted_non_ds_info(self):
        human_accepted = self._make_redaction(
            is_accepted=True, decided_by=Redaction.DecidedBy.HUMAN
        )
        machine_accepted = self._make_redaction(
            is_accepted=True, decided_by=Redaction.DecidedBy.AUTO_ACCEPT
        )
        ds_info = self._make_redaction(
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
        )
        rejected = self._make_redaction(
            justification="reason", decided_by=Redaction.DecidedBy.HUMAN
        )
        pending = self._make_redaction()

        trainable = Redaction.objects.trainable()
        self.assertIn(human_accepted, trainable)
        self.assertNotIn(machine_accepted, trainable)
        self.assertNotIn(ds_info, trainable)
        self.assertNotIn(rejected, trainable)
        self.assertNotIn(pending, trainable)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class DisclosureLockTests(NetworkBlockerMixin, TestCase):
    """
    Post-disclosure lock at the RedactionQuerySet decision choke point: once a
    case has a preserved Export, human decision writes are refused unless an
    Internal Review is open. System writes and undisclosed cases are exempt.
    """

    def setUp(self):
        self.case = Case.objects.create(
            case_reference="202560", data_subject_name="Lock Test"
        )
        file = SimpleUploadedFile("lock.txt", b"content")
        self.document = Document.objects.create(
            case=self.case, original_file=file
        )
        self.redaction = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=4,
            text="test",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _disclose(self, sequence=1):
        """Preserve a disclosure export so the case counts as disclosed."""
        return Export.objects.create(
            case=self.case,
            export_file=SimpleUploadedFile("d.zip", b"zip"),
            sequence=sequence,
            label="Original disclosure",
        )

    def _open_review(self):
        return InternalReview.objects.create(
            case=self.case, status=InternalReview.Status.OPEN
        )

    def _qs(self):
        return Redaction.objects.filter(pk=self.redaction.pk)

    # ---- undisclosed case: writes always allowed ----
    def test_human_accept_allowed_when_not_disclosed(self):
        self._qs().accept(by=Redaction.DecidedBy.HUMAN)
        self.redaction.refresh_from_db()
        self.assertTrue(self.redaction.is_accepted)

    # ---- disclosed, no open review: human writes refused ----
    def test_human_accept_refused_when_disclosed_and_no_review(self):
        self._disclose()
        with self.assertRaises(DisclosureLockError):
            self._qs().accept(by=Redaction.DecidedBy.HUMAN)

    def test_human_reject_refused_when_disclosed_and_no_review(self):
        self._disclose()
        with self.assertRaises(DisclosureLockError):
            self._qs().reject("reason", by=Redaction.DecidedBy.HUMAN)

    def test_reset_refused_when_disclosed_and_no_review(self):
        self._disclose()
        with self.assertRaises(DisclosureLockError):
            self._qs().reset()

    def test_lock_error_is_a_provenance_error(self):
        """Existing ProvenanceError handlers also catch the lock."""
        self._disclose()
        with self.assertRaises(ProvenanceError):
            self._qs().accept(by=Redaction.DecidedBy.HUMAN)

    # ---- disclosed, review open: full edit scope restored ----
    def test_human_accept_allowed_while_review_open(self):
        self._disclose()
        self._open_review()
        self._qs().accept(by=Redaction.DecidedBy.HUMAN)
        self.redaction.refresh_from_db()
        self.assertTrue(self.redaction.is_accepted)

    def test_human_reject_allowed_while_review_open(self):
        self._disclose()
        self._open_review()
        self._qs().reject("reason", by=Redaction.DecidedBy.HUMAN)
        self.redaction.refresh_from_db()
        self.assertFalse(self.redaction.is_accepted)
        self.assertEqual(self.redaction.justification, "reason")

    def test_reset_allowed_while_review_open(self):
        self._disclose()
        self._open_review()
        self._qs().reset()
        self.redaction.refresh_from_db()
        self.assertIsNone(self.redaction.decided_by)

    def test_closed_review_does_not_unlock(self):
        self._disclose()
        InternalReview.objects.create(
            case=self.case, status=InternalReview.Status.COMPLETED
        )
        with self.assertRaises(DisclosureLockError):
            self._qs().accept(by=Redaction.DecidedBy.HUMAN)

    # ---- system writes: exempt regardless of disclosure ----
    def test_system_actors_exempt_when_disclosed(self):
        self._disclose()
        for actor in (
            Redaction.DecidedBy.AUTO_ACCEPT,
            Redaction.DecidedBy.CASE_PROPAGATION,
            Redaction.DecidedBy.DS_INFO_PROPAGATION,
        ):
            with self.subTest(actor=actor):
                self._qs().accept(by=actor)
                self.redaction.refresh_from_db()
                self.assertTrue(self.redaction.is_accepted)

    def test_system_actor_write_runs_no_lock_queries(self):
        """System writes short-circuit before touching the database."""
        self._disclose()
        with self.assertNumQueries(1):  # only the UPDATE itself
            self._qs().accept(by=Redaction.DecidedBy.AUTO_ACCEPT)

    def test_empty_queryset_is_allowed_when_disclosed(self):
        self._disclose()
        # Matches no rows; must not raise even though the case is disclosed.
        count = Redaction.objects.filter(pk=uuid.uuid4()).accept(
            by=Redaction.DecidedBy.HUMAN
        )
        self.assertEqual(count, 0)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RedactionContextModelTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="202530", data_subject_name="Context Test"
        )
        file = SimpleUploadedFile("context.txt", b"file_content")
        self.document = Document.objects.create(
            case=self.case, original_file=file
        )
        self.redaction = Redaction.objects.create(
            document=self.document, start_char=0, end_char=4, text="test"
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


class DocumentExportSettingsModelTests(NetworkBlockerMixin, TestCase):
    def test_get_creates_default_row(self):
        self.assertEqual(DocumentExportSettings.objects.count(), 0)
        obj = DocumentExportSettings.get()
        self.assertEqual(DocumentExportSettings.objects.count(), 1)
        self.assertEqual(obj.pk, 1)

    def test_get_returns_same_row_on_repeat_calls(self):
        obj1 = DocumentExportSettings.get()
        obj2 = DocumentExportSettings.get()
        self.assertEqual(obj1.pk, obj2.pk)
        self.assertEqual(DocumentExportSettings.objects.count(), 1)

    def test_save_forces_pk_1(self):
        obj = DocumentExportSettings(header_text="TEST")
        obj.save()
        self.assertEqual(obj.pk, 1)
        self.assertEqual(DocumentExportSettings.objects.count(), 1)

    def test_default_field_values(self):
        obj = DocumentExportSettings.get()
        self.assertEqual(obj.header_text, "")
        self.assertEqual(obj.footer_text, "")
        self.assertEqual(obj.watermark_text, "")
        self.assertFalse(obj.watermark_include_case_ref)
        self.assertFalse(obj.page_numbers_enabled)

    def test_default_font_family(self):
        obj = DocumentExportSettings.get()
        self.assertEqual(obj.font_family, "arial")

    def test_font_family_css_property(self):
        obj = DocumentExportSettings.get()
        obj.font_family = DocumentExportSettings.FontFamily.ARIAL
        self.assertEqual(obj.font_family_css, "Arial, sans-serif")
        obj.font_family = DocumentExportSettings.FontFamily.TIMES_NEW_ROMAN
        self.assertEqual(obj.font_family_css, '"Times New Roman", serif')
        obj.font_family = DocumentExportSettings.FontFamily.COURIER_NEW
        self.assertEqual(obj.font_family_css, '"Courier New", monospace')
        obj.font_family = DocumentExportSettings.FontFamily.GEORGIA
        self.assertEqual(obj.font_family_css, "Georgia, serif")
        obj.font_family = DocumentExportSettings.FontFamily.VERDANA
        self.assertEqual(obj.font_family_css, "Verdana, sans-serif")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ExportModelTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="250099", data_subject_name="Jane Roe"
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_sequence_unique_per_case(self):
        Export.objects.create(case=self.case, sequence=1, label="Original")
        with self.assertRaises(IntegrityError):
            Export.objects.create(
                case=self.case, sequence=1, label="Duplicate"
            )

    def test_same_sequence_allowed_across_cases(self):
        other = Case.objects.create(
            case_reference="250100", data_subject_name="John Doe"
        )
        Export.objects.create(case=self.case, sequence=1, label="A")
        Export.objects.create(case=other, sequence=1, label="B")
        self.assertEqual(Export.objects.filter(sequence=1).count(), 2)

    def test_exports_ordered_by_sequence(self):
        Export.objects.create(case=self.case, sequence=2, label="Two")
        Export.objects.create(case=self.case, sequence=1, label="One")
        self.assertEqual([e.sequence for e in self.case.exports.all()], [1, 2])

    def test_review_link_optional(self):
        review = InternalReview.objects.create(case=self.case)
        export = Export.objects.create(
            case=self.case, sequence=1, label="Original", review=review
        )
        self.assertEqual(export.review, review)
        self.assertIn(export, review.exports.all())


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class InternalReviewModelTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="250099", data_subject_name="Jane Roe"
        )

    def test_defaults_to_open(self):
        review = InternalReview.objects.create(case=self.case)
        self.assertEqual(review.status, InternalReview.Status.OPEN)
        self.assertIsNotNone(review.opened_at)
        self.assertIsNone(review.closed_at)
        self.assertEqual(review.outcome, "")

    def test_reviews_ordered_newest_first(self):
        first = InternalReview.objects.create(case=self.case)
        second = InternalReview.objects.create(case=self.case)
        self.assertEqual(list(self.case.reviews.all()), [second, first])
