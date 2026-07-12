import itertools
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from training.tests.base import NetworkBlockerMixin

from ..models import Case, Document, Redaction
from ..span_merging import (
    MergePair,
    compute_review_merge_pairs,
    merge_spans_for_removal,
    serialize_merge_structure,
)

User = get_user_model()

FIXTURES = Path(__file__).parent / "fixtures"


def span(id, start, end, rtype="OP_DATA", **extra):
    return SimpleNamespace(
        id=id,
        start_char=start,
        end_char=end,
        redaction_type=rtype,
        **extra,
    )


class ComputeReviewMergePairsTests(SimpleTestCase):
    """Pair emission — ports the mergeRedactionSpans.cy.js rule expectations."""

    def test_empty_input_yields_no_pairs(self):
        self.assertEqual(compute_review_merge_pairs([]), [])

    def test_single_span_yields_no_pairs(self):
        self.assertEqual(compute_review_merge_pairs([span("a", 0, 5)]), [])

    def test_immediately_adjacent_same_type_pair(self):
        pairs = compute_review_merge_pairs([span("a", 0, 5), span("b", 5, 10)])
        self.assertEqual(
            pairs,
            [MergePair(a="a", b="b", type="OP_DATA", joiner="", blockers=())],
        )

    def test_gap_of_two_pairs_with_space_joiner(self):
        pairs = compute_review_merge_pairs([span("a", 0, 5), span("b", 7, 12)])
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].joiner, " ")

    def test_gap_of_three_yields_no_pair(self):
        pairs = compute_review_merge_pairs([span("a", 0, 5), span("b", 8, 13)])
        self.assertEqual(pairs, [])

    def test_different_types_never_pair(self):
        pairs = compute_review_merge_pairs(
            [span("a", 0, 5, "OP_DATA"), span("b", 5, 10, "PII")]
        )
        self.assertEqual(pairs, [])

    def test_three_span_chain_emits_consecutive_pairs(self):
        pairs = compute_review_merge_pairs(
            [span("a", 0, 3), span("b", 3, 6), span("c", 6, 9)]
        )
        self.assertEqual([(p.a, p.b) for p in pairs], [("a", "b"), ("b", "c")])

    def test_unsorted_input_is_sorted_before_pairing(self):
        pairs = compute_review_merge_pairs([span("b", 5, 10), span("a", 0, 5)])
        self.assertEqual([(p.a, p.b) for p in pairs], [("a", "b")])

    def test_close_same_type_spans_carry_intervening_blocker(self):
        # A(PII) X(OP_DATA) B(PII): the A-B pair exists (gap 2) but names X
        # as a blocker, so the client only activates it once X has left the
        # pending section (the intervening-different-type edge case).
        pairs = compute_review_merge_pairs(
            [
                span("A", 0, 5, "PII"),
                span("X", 5, 7, "OP_DATA"),
                span("B", 7, 12, "PII"),
            ]
        )
        self.assertEqual(
            pairs,
            [MergePair(a="A", b="B", type="PII", joiner=" ", blockers=("X",))],
        )

    def test_same_type_span_between_endpoints_is_also_a_blocker(self):
        # Chain a,b,c where a-c are also within the gap rule: the skip pair
        # (a, c) must name b, so it can only activate when b leaves the
        # section — never producing a group that jumps over an in-section span.
        pairs = compute_review_merge_pairs(
            [span("a", 0, 5), span("b", 5, 7), span("c", 7, 12)]
        )
        by_endpoints = {(p.a, p.b): p for p in pairs}
        self.assertEqual(
            set(by_endpoints), {("a", "b"), ("b", "c"), ("a", "c")}
        )
        self.assertEqual(by_endpoints[("a", "c")].blockers, ("b",))
        self.assertEqual(by_endpoints[("a", "b")].blockers, ())
        self.assertEqual(by_endpoints[("b", "c")].blockers, ())

    def test_pairs_are_status_independent(self):
        """Permuting decision state across a fixture yields identical pairs."""
        base = [
            span("a", 0, 5, "PII"),
            span("x", 5, 7, "OP_DATA"),
            span("b", 7, 12, "PII"),
            span("c", 14, 20, "PII"),
        ]
        decisions = [
            (False, None),
            (True, None),
            (False, "disclosable"),
        ]
        baseline = None
        for combo in itertools.product(decisions, repeat=len(base)):
            for s, (accepted, justification) in zip(base, combo, strict=True):
                s.is_accepted = accepted
                s.justification = justification
            pairs = compute_review_merge_pairs(base)
            if baseline is None:
                baseline = pairs
            self.assertEqual(pairs, baseline)

    def test_golden_fixture_redactions_produce_golden_pairs(self):
        """Shared fixture: the Cypress side asserts pairs -> groups; this
        side asserts redactions -> pairs. Composition equals the old
        end-to-end frontend merge behaviour."""
        golden = json.loads(
            (FIXTURES / "span_merging_review_golden.json").read_text()
        )
        redactions = [
            span(r["id"], r["start_char"], r["end_char"], r["redaction_type"])
            for r in golden["redactions"]
        ]
        self.assertEqual(
            serialize_merge_structure(redactions),
            {"version": 1, "pairs": golden["pairs"]},
        )

    def test_frontend_golden_fixture_copy_in_sync(self):
        """The Cypress copy of the shared fixture must stay byte-identical
        to the canonical one so both sides keep testing the same contract."""
        frontend_copy = (
            Path(__file__).resolve().parents[2]
            / "frontend"
            / "cypress"
            / "fixtures"
            / "span_merging_review_golden.json"
        )
        self.assertEqual(
            (FIXTURES / "span_merging_review_golden.json").read_text(),
            frontend_copy.read_text(),
        )


class MergeSpansForRemovalTests(SimpleTestCase):
    """Export removal merging — moved verbatim from services (and its tests)."""

    def test_single_redaction_single_span(self):
        text = "Hello world foo bar"
        spans = merge_spans_for_removal(text, 0, len(text), [span("r", 6, 11)])
        self.assertEqual(spans, [[6, 11]])

    def test_whitespace_gap_merged(self):
        text = "John Smith was here"
        spans = merge_spans_for_removal(
            text, 0, len(text), [span("r1", 0, 4), span("r2", 5, 10)]
        )
        self.assertEqual(spans, [[0, 10]])

    def test_word_gap_kept_separate(self):
        text = "John went to London"
        spans = merge_spans_for_removal(
            text, 0, len(text), [span("r1", 0, 4), span("r2", 13, 19)]
        )
        self.assertEqual(spans, [[0, 4], [13, 19]])

    def test_comma_separator_merged(self):
        text = "John, Smith"
        spans = merge_spans_for_removal(
            text, 0, len(text), [span("r1", 0, 4), span("r2", 6, 11)]
        )
        self.assertEqual(spans, [[0, 11]])

    def test_colon_separator_merged(self):
        text = "LPU: Chester"
        spans = merge_spans_for_removal(
            text, 0, len(text), [span("r1", 0, 3), span("r2", 5, 12)]
        )
        self.assertEqual(spans, [[0, 12]])

    def test_hash_prefix_absorbed(self):
        text = "ref #42/12345 noted"
        spans = merge_spans_for_removal(text, 0, len(text), [span("r", 5, 13)])
        self.assertEqual(spans, [[4, 13]])

    def test_golden_export_regression(self):
        """Byte-identical to the pre-relocation services.py behaviour,
        captured in the checked-in fixture before the move."""
        from ..services import _apply_redactions_to_segment

        golden = json.loads(
            (FIXTURES / "span_merging_export_golden.json").read_text()
        )
        text = golden["text"]
        for case in golden["cases"]:
            redactions = [
                span(f"r{i}", s, e, rtype)
                for i, (s, e, rtype) in enumerate(case["redactions"])
            ]
            with self.subTest(case=case["name"]):
                self.assertEqual(
                    merge_spans_for_removal(
                        text, case["seg_start"], case["seg_end"], redactions
                    ),
                    case["merged_spans"],
                )
                self.assertEqual(
                    _apply_redactions_to_segment(
                        text,
                        case["seg_start"],
                        case["seg_end"],
                        redactions,
                        "removal",
                    ),
                    case["removal_html"],
                )


class MergeStructureContractTests(NetworkBlockerMixin, APITestCase):
    """The merge_structure API envelope on the review and redaction views."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="password"
        )
        self.client.force_authenticate(user=self.user)
        self.case = Case.objects.create(
            case_reference="250001",
            data_subject_name="John Doe",
            data_subject_dob=date(1990, 1, 1),
            created_by=self.user,
        )
        self.document = Document.objects.create(
            case=self.case,
            extracted_text="Alpha  Bravo and more text follows here.",
            status=Document.Status.READY_FOR_REVIEW,
        )
        self.r1 = Redaction.objects.create(
            document=self.document,
            start_char=0,
            end_char=5,
            text="Alpha",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        self.r2 = Redaction.objects.create(
            document=self.document,
            start_char=7,
            end_char=12,
            text="Bravo",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )

    def _expected_structure(self):
        return {
            "version": 1,
            "pairs": [
                {
                    "a": str(self.r1.id),
                    "b": str(self.r2.id),
                    "type": "PII",
                    "joiner": " ",
                    "blockers": [],
                }
            ],
        }

    def test_review_response_carries_merge_structure(self):
        url = reverse(
            "document-review",
            kwargs={"case_id": self.case.id, "document_id": self.document.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["merge_structure"], self._expected_structure()
        )

    def test_redaction_list_plain_response_unchanged(self):
        url = reverse(
            "redaction-list-create",
            kwargs={"document_id": self.document.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertNotIn("merge_structure", response.data)

    def test_redaction_list_include_merge_structure_envelope(self):
        url = reverse(
            "redaction-list-create",
            kwargs={"document_id": self.document.id},
        )
        response = self.client.get(url, {"include": "merge_structure"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["redactions"]), 2)
        self.assertEqual(
            response.data["merge_structure"], self._expected_structure()
        )

    def test_redaction_list_scoped_to_document(self):
        other_document = Document.objects.create(
            case=self.case,
            extracted_text="Unrelated text",
            status=Document.Status.READY_FOR_REVIEW,
        )
        Redaction.objects.create(
            document=other_document,
            start_char=0,
            end_char=9,
            text="Unrelated",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        url = reverse(
            "redaction-list-create",
            kwargs={"document_id": self.document.id},
        )
        response = self.client.get(url)
        self.assertEqual(
            {r["id"] for r in response.data},
            {str(self.r1.id), str(self.r2.id)},
        )
