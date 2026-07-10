import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from training.tests.base import NetworkBlockerMixin

from ..ds_info_propagation import (
    apply_plan,
    build_term_patterns,
    plan_document,
    propagate_term_across_case,
    propagate_terms_to_document,
)
from ..models import Case, Document, Redaction

MEDIA_ROOT = tempfile.mkdtemp()


class BuildTermPatternsTests(SimpleTestCase):
    """build_term_patterns is pure — no DB needed."""

    def test_expands_plural_form(self):
        (pattern,) = build_term_patterns(["party"])
        self.assertIsNotNone(pattern.regex.search("the parties met"))
        self.assertIsNotNone(pattern.regex.search("the party met"))

    def test_expands_singular_form(self):
        (pattern,) = build_term_patterns(["parties"])
        self.assertIsNotNone(pattern.regex.search("the party met"))

    def test_variations_sorted_longest_first(self):
        (pattern,) = build_term_patterns(["data subject"])
        match = pattern.regex.search("the data subjects met")
        self.assertEqual(match.group(0), "data subjects")

    def test_filters_blank_terms(self):
        self.assertEqual(build_term_patterns(["", "   ", None]), [])

    def test_escapes_regex_metacharacters(self):
        (pattern,) = build_term_patterns(["A.B"])
        self.assertIsNotNone(pattern.regex.search("codename A.B here"))
        self.assertIsNone(pattern.regex.search("codename AXB here"))

    def test_matches_whole_words_only(self):
        (pattern,) = build_term_patterns(["name"])
        self.assertIsNone(pattern.regex.search("her surname was"))
        self.assertIsNotNone(pattern.regex.search("her name was"))

    def test_case_insensitive_match_returns_original_case(self):
        (pattern,) = build_term_patterns(["alice"])
        match = pattern.regex.search("Then ALICE spoke")
        self.assertEqual(match.group(0), "ALICE")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PlanApplyTestCase(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.case = Case.objects.create(
            case_reference="DSP01",
            data_subject_name="Test Subject",
        )
        self.document = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("a.pdf", b"x", "application/pdf"),
            status=Document.Status.READY_FOR_REVIEW,
            extracted_text="Alice spoke to Bob about the party.",
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _redaction(self, start, end, text, redaction_type, accepted=False):
        return Redaction.objects.create(
            document=self.document,
            start_char=start,
            end_char=end,
            text=text,
            redaction_type=redaction_type,
            is_accepted=accepted,
            decided_by=Redaction.DecidedBy.HUMAN if accepted else None,
        )


class PlanDocumentTests(PlanApplyTestCase):
    def test_unclaimed_span_planned_as_create(self):
        plan = plan_document(self.document, build_term_patterns(["Alice"]))

        self.assertEqual(len(plan.to_create), 1)
        created = plan.to_create[0]
        self.assertEqual((created.start_char, created.end_char), (0, 5))
        self.assertEqual(created.text, "Alice")
        self.assertEqual(
            created.redaction_type, Redaction.RedactionType.DS_INFORMATION
        )
        self.assertTrue(created.is_accepted)
        self.assertTrue(created.is_suggestion)
        self.assertEqual(plan.to_accept, [])
        self.assertEqual(plan.to_upgrade, [])
        self.assertEqual(plan.ids_to_delete, [])

    def test_unaccepted_ds_info_planned_as_accept(self):
        existing = self._redaction(
            0, 5, "Alice", Redaction.RedactionType.DS_INFORMATION
        )

        plan = plan_document(self.document, build_term_patterns(["Alice"]))

        self.assertEqual(plan.to_accept, [existing])
        self.assertEqual(plan.to_create, [])
        self.assertEqual(plan.to_upgrade, [])
        self.assertEqual(plan.ids_to_delete, [])

    def test_accepted_ds_info_produces_empty_plan(self):
        self._redaction(
            0,
            5,
            "Alice",
            Redaction.RedactionType.DS_INFORMATION,
            accepted=True,
        )

        plan = plan_document(self.document, build_term_patterns(["Alice"]))

        self.assertTrue(plan.is_empty)

    def test_other_type_at_span_planned_as_upgrade(self):
        existing = self._redaction(
            0, 5, "Alice", Redaction.RedactionType.THIRD_PARTY_PII
        )

        plan = plan_document(self.document, build_term_patterns(["Alice"]))

        self.assertEqual(plan.to_upgrade, [existing])
        self.assertEqual(plan.to_create, [])
        self.assertEqual(plan.to_accept, [])
        self.assertEqual(plan.ids_to_delete, [])

    def test_duplicates_at_ds_info_span_planned_for_deletion(self):
        self._redaction(0, 5, "Alice", Redaction.RedactionType.DS_INFORMATION)
        dup_ds = self._redaction(
            0, 5, "Alice", Redaction.RedactionType.DS_INFORMATION
        )
        dup_other = self._redaction(
            0, 5, "Alice", Redaction.RedactionType.THIRD_PARTY_PII
        )

        plan = plan_document(self.document, build_term_patterns(["Alice"]))

        self.assertCountEqual(plan.ids_to_delete, [dup_ds.id, dup_other.id])

    def test_duplicate_other_types_at_span_planned_for_deletion(self):
        self._redaction(0, 5, "Alice", Redaction.RedactionType.THIRD_PARTY_PII)
        dup = self._redaction(
            0, 5, "Alice", Redaction.RedactionType.OPERATIONAL_DATA
        )

        plan = plan_document(self.document, build_term_patterns(["Alice"]))

        self.assertEqual(len(plan.to_upgrade), 1)
        self.assertEqual(plan.ids_to_delete, [dup.id])

    def test_earlier_term_claims_overlapping_span(self):
        # Both terms match "Alice" at (0, 5); only one create is planned.
        plan = plan_document(
            self.document, build_term_patterns(["Alice", "alice"])
        )

        self.assertEqual(len(plan.to_create), 1)

    def test_document_without_extracted_text_returns_empty_plan(self):
        self.document.extracted_text = None

        plan = plan_document(self.document, build_term_patterns(["Alice"]))

        self.assertTrue(plan.is_empty)

    def test_no_match_performs_zero_queries(self):
        patterns = build_term_patterns(["Zebediah"])

        with self.assertNumQueries(0):
            plan = plan_document(self.document, patterns)

        self.assertTrue(plan.is_empty)


class ApplyPlanTests(PlanApplyTestCase):
    def test_empty_plan_performs_zero_queries(self):
        plan = plan_document(self.document, build_term_patterns(["Zebediah"]))

        with self.assertNumQueries(0):
            apply_plan(plan)

    def test_persists_creates_accepts_upgrades_and_deletes(self):
        to_accept = self._redaction(
            0, 5, "Alice", Redaction.RedactionType.DS_INFORMATION
        )
        to_delete = self._redaction(
            0, 5, "Alice", Redaction.RedactionType.THIRD_PARTY_PII
        )
        to_upgrade = self._redaction(
            15, 18, "Bob", Redaction.RedactionType.THIRD_PARTY_PII
        )

        plan = plan_document(
            self.document, build_term_patterns(["Alice", "Bob", "party"])
        )
        apply_plan(plan)

        to_accept.refresh_from_db()
        self.assertTrue(to_accept.is_accepted)
        self.assertIsNone(to_accept.justification)

        to_upgrade.refresh_from_db()
        self.assertEqual(
            to_upgrade.redaction_type, Redaction.RedactionType.DS_INFORMATION
        )
        self.assertTrue(to_upgrade.is_accepted)
        self.assertTrue(to_upgrade.is_suggestion)

        self.assertFalse(Redaction.objects.filter(id=to_delete.id).exists())

        created = self.document.redactions.get(text="party")
        self.assertEqual(
            created.redaction_type, Redaction.RedactionType.DS_INFORMATION
        )
        self.assertTrue(created.is_accepted)

    def test_write_query_count_is_constant(self):
        # No deletes here: auditlog's per-object delete signals make the
        # delete branch O(n); creates and updates stay constant via bulk ops.
        self._redaction(0, 5, "Alice", Redaction.RedactionType.DS_INFORMATION)
        self._redaction(15, 18, "Bob", Redaction.RedactionType.THIRD_PARTY_PII)

        plan = plan_document(
            self.document, build_term_patterns(["Alice", "Bob", "party"])
        )

        # Savepoint + one bulk_create + one bulk_update + one accept
        # UPDATE + release.
        with self.assertNumQueries(5):
            apply_plan(plan)

    def test_failure_rolls_back_whole_document(self):
        to_accept = self._redaction(
            0, 5, "Alice", Redaction.RedactionType.DS_INFORMATION
        )
        to_delete = self._redaction(
            0, 5, "Alice", Redaction.RedactionType.THIRD_PARTY_PII
        )

        plan = plan_document(
            self.document, build_term_patterns(["Alice", "party"])
        )

        with patch(
            "cases.models.RedactionQuerySet.accept",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                apply_plan(plan)

        # The delete and create that ran before the failure were rolled back.
        self.assertTrue(Redaction.objects.filter(id=to_delete.id).exists())
        self.assertFalse(
            self.document.redactions.filter(text="party").exists()
        )
        to_accept.refresh_from_db()
        self.assertFalse(to_accept.is_accepted)


class ScopeConvenienceTests(PlanApplyTestCase):
    def setUp(self):
        super().setUp()
        self.other_document = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("b.pdf", b"y", "application/pdf"),
            status=Document.Status.COMPLETED,
            extracted_text="Alice was also mentioned here.",
        )

    def test_propagate_terms_to_document_scans_one_document(self):
        propagate_terms_to_document(self.document, ["Alice"])

        self.assertTrue(self.document.redactions.filter(text="Alice").exists())
        self.assertFalse(self.other_document.redactions.exists())

    def test_propagate_terms_to_document_with_blank_terms_is_noop(self):
        with self.assertNumQueries(0):
            propagate_terms_to_document(self.document, ["", "  "])

    def test_propagate_term_across_case_scans_other_documents(self):
        source = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=5,
            text="Alice",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )

        propagate_term_across_case(source)

        propagated = self.other_document.redactions.get(text="Alice")
        self.assertEqual(
            propagated.redaction_type, Redaction.RedactionType.DS_INFORMATION
        )
        self.assertTrue(propagated.is_accepted)
        # The source document itself is not rescanned.
        self.assertEqual(self.document.redactions.count(), 1)

    def test_propagate_term_across_case_skips_processing_documents(self):
        Document.objects.filter(id=self.other_document.id).update(
            status=Document.Status.PROCESSING
        )
        source = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=5,
            text="Alice",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )

        propagate_term_across_case(source)

        self.assertFalse(self.other_document.redactions.exists())

    def test_propagate_term_across_case_blank_term_is_noop(self):
        source = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=1,
            text=" ",
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
            is_accepted=True,
            decided_by=Redaction.DecidedBy.HUMAN,
        )

        with self.assertNumQueries(0):
            propagate_term_across_case(source)
