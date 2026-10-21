from django.test import SimpleTestCase

from ..disclosure import SpanPiece, disclosed_ranges, withheld_spans
from ..models import Redaction

DS = Redaction.RedactionType.DS_INFORMATION
OP = Redaction.RedactionType.OPERATIONAL_DATA
TP = Redaction.RedactionType.THIRD_PARTY_PII


class _Context:
    def __init__(self, text):
        self.text = text


class _Span:
    """A stand-in for an accepted Redaction — offsets, type, optional context."""

    def __init__(self, start, end, redaction_type, context=None):
        self.start_char = start
        self.end_char = end
        self.redaction_type = redaction_type
        if context is not None:
            self.context = _Context(context)


def _offsets(pieces):
    return [(p.start_char, p.end_char) for p in pieces]


class DisclosedRangesTests(SimpleTestCase):
    def test_collects_only_ds_info(self):
        spans = [_Span(0, 5, OP), _Span(10, 15, DS), _Span(20, 25, TP)]

        self.assertEqual(disclosed_ranges(spans), [[10, 15]])

    def test_merges_overlapping_ds_info(self):
        spans = [_Span(10, 20, DS), _Span(15, 25, DS)]

        self.assertEqual(disclosed_ranges(spans), [[10, 25]])

    def test_merges_abutting_ds_info(self):
        spans = [_Span(10, 20, DS), _Span(20, 30, DS)]

        self.assertEqual(disclosed_ranges(spans), [[10, 30]])

    def test_keeps_disjoint_ds_info_separate(self):
        spans = [_Span(30, 40, DS), _Span(10, 20, DS)]

        self.assertEqual(disclosed_ranges(spans), [[10, 20], [30, 40]])

    def test_no_ds_info_is_empty(self):
        self.assertEqual(disclosed_ranges([_Span(0, 5, OP)]), [])


class WithheldSpansTests(SimpleTestCase):
    def test_ds_info_is_never_withheld(self):
        self.assertEqual(withheld_spans([_Span(0, 5, DS)]), [])

    def test_span_not_overlapping_ds_info_is_untouched(self):
        span = _Span(0, 5, OP)

        self.assertEqual(withheld_spans([span, _Span(10, 15, DS)]), [span])

    def test_without_ds_info_spans_pass_through_unchanged(self):
        """The original rows are returned, not copies — nothing to subtract."""
        a, b = _Span(10, 15, OP), _Span(0, 5, TP)

        self.assertEqual(withheld_spans([a, b]), [b, a])

    def test_interior_ds_info_splits_the_withholding_span(self):
        """'JONES, Michael #0712345' with 'Michael' disclosed inside it."""
        pieces = withheld_spans([_Span(9, 32, OP), _Span(16, 23, DS)])

        self.assertEqual(_offsets(pieces), [(9, 16), (23, 32)])
        self.assertTrue(all(p.redaction_type == OP for p in pieces))

    def test_ds_info_at_the_start_trims_the_front(self):
        pieces = withheld_spans([_Span(9, 32, OP), _Span(9, 16, DS)])

        self.assertEqual(_offsets(pieces), [(16, 32)])

    def test_ds_info_at_the_end_trims_the_back(self):
        pieces = withheld_spans([_Span(9, 32, OP), _Span(23, 32, DS)])

        self.assertEqual(_offsets(pieces), [(9, 23)])

    def test_ds_info_covering_the_whole_span_removes_it(self):
        self.assertEqual(
            withheld_spans([_Span(9, 32, OP), _Span(9, 32, DS)]), []
        )

    def test_ds_info_wider_than_the_span_removes_it(self):
        self.assertEqual(
            withheld_spans([_Span(12, 20, OP), _Span(9, 32, DS)]), []
        )

    def test_two_interior_claims_split_the_span_into_three(self):
        pieces = withheld_spans(
            [_Span(0, 40, OP), _Span(10, 15, DS), _Span(25, 30, DS)]
        )

        self.assertEqual(_offsets(pieces), [(0, 10), (15, 25), (30, 40)])

    def test_one_claim_cuts_every_overlapping_span(self):
        pieces = withheld_spans(
            [_Span(0, 20, OP), _Span(10, 30, TP), _Span(12, 18, DS)]
        )

        self.assertEqual(
            _offsets(pieces), [(0, 12), (10, 12), (18, 20), (18, 30)]
        )

    def test_result_is_sorted_by_position(self):
        pieces = withheld_spans(
            [_Span(30, 40, OP), _Span(0, 10, TP), _Span(5, 7, DS)]
        )

        self.assertEqual(_offsets(pieces), [(0, 5), (7, 10), (30, 40)])


class SpanPieceContextTests(SimpleTestCase):
    def test_piece_without_context_has_no_context_attribute(self):
        """The export renderers branch on hasattr, so it must be absent."""
        self.assertFalse(hasattr(SpanPiece(0, 5, OP), "context"))

    def test_piece_with_context_exposes_it(self):
        piece = SpanPiece(0, 5, OP, context=_Context("why"))

        self.assertEqual(piece.context.text, "why")

    def test_first_piece_keeps_the_context_note(self):
        [first, second] = withheld_spans(
            [_Span(0, 20, OP, context="exempt"), _Span(5, 10, DS)]
        )

        self.assertEqual(first.context.text, "exempt")
        self.assertFalse(hasattr(second, "context"))

    def test_a_trimmed_front_drops_the_context_note(self):
        """The piece no longer starts the span, so it is not its opening."""
        [piece] = withheld_spans(
            [_Span(0, 20, OP, context="exempt"), _Span(0, 5, DS)]
        )

        self.assertFalse(hasattr(piece, "context"))
