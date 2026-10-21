"""
Whose characters win when two accepted redactions cover the same text.

DS_INFO is not a redaction in the way the other types are.  The other types
say "withhold these characters"; DS_INFO says "these characters are the data
subject's own, so they go out in the clear".  The two are therefore in direct
competition whenever their spans overlap, and the overlap is common: a
detector marks ``JONES, Michael #0712345`` as one operational string, and a
reviewer marks ``Michael`` within it as the data subject's name.

Removing the DS_INFO row from the export (which is all the export used to do)
only honours the decision when the spans coincide exactly.  On a partial
overlap the wider withholding span still covers the characters, so the
reviewer's decision silently does nothing and the data subject's own name is
blacked out in their own disclosure.

So DS_INFO wins on exactly the characters it covers, and no more.  A
withholding span overlapping it is cut back to the parts the data subject's
own information does not claim — split in two where the claim is interior.
What surrounds the name stays withheld, because what made it redactable
(an operational marking, a third party's details) is still there; a reviewer
who judges the remainder disclosable removes it in review.
"""

from .models import Redaction


class SpanPiece:
    """What is left of one redaction after the disclosed characters are cut out.

    Stands in for a ``Redaction`` in the export renderers, which read only a
    span's offsets, its type and its optional context note.  A piece carries
    ``context`` only when it starts where the original span started, so a
    split span annotates its first piece and not every piece.

    ``__slots__`` rather than a dataclass on purpose: the renderers ask
    ``hasattr(r, "context")``, and an unset slot has no attribute to find,
    whereas a dataclass field would leave its default behind on the class.
    """

    __slots__ = ("start_char", "end_char", "redaction_type", "context")

    def __init__(self, start_char, end_char, redaction_type, context=None):
        self.start_char = start_char
        self.end_char = end_char
        self.redaction_type = redaction_type
        if context is not None:
            self.context = context

    def __repr__(self):
        return (
            f"SpanPiece({self.start_char}, {self.end_char}, "
            f"{self.redaction_type!r})"
        )


def _merge_ranges(ranges):
    """Collapse a list of (start, end) pairs into sorted, non-overlapping ones."""
    merged = []
    for start, end in sorted(ranges):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _subtract(start, end, disclosed):
    """The parts of [start, end) left once every disclosed range is removed.

    *disclosed* must be sorted and non-overlapping (see :func:`_merge_ranges`).
    """
    remaining = []
    cursor = start
    for d_start, d_end in disclosed:
        if d_end <= cursor:
            continue
        if d_start >= end:
            break
        if d_start > cursor:
            remaining.append((cursor, d_start))
        cursor = max(cursor, d_end)
        if cursor >= end:
            break
    if cursor < end:
        remaining.append((cursor, end))
    return remaining


def disclosed_ranges(redactions):
    """The character ranges accepted DS_INFO claims, merged and sorted."""
    return _merge_ranges(
        [
            [r.start_char, r.end_char]
            for r in redactions
            if r.redaction_type == Redaction.RedactionType.DS_INFORMATION
        ]
    )


def withheld_spans(redactions):
    """Resolve accepted redactions into the spans an export should withhold.

    Drops DS_INFO (its characters are disclosed, not withheld) and cuts every
    other span back to the characters DS_INFO does not claim.  A span wholly
    claimed by DS_INFO disappears; one claimed through the middle comes back
    as two pieces.

    Returns pieces sorted by position, which is the order the export
    renderers require.
    """
    disclosed = disclosed_ranges(redactions)
    pieces = []
    for r in redactions:
        if r.redaction_type == Redaction.RedactionType.DS_INFORMATION:
            continue
        remaining = _subtract(r.start_char, r.end_char, disclosed)
        if remaining == [(r.start_char, r.end_char)]:
            # Nothing was claimed from it — keep the row itself rather than
            # rebuilding an equivalent piece.
            pieces.append(r)
            continue
        for start, end in remaining:
            pieces.append(
                SpanPiece(
                    start_char=start,
                    end_char=end,
                    redaction_type=r.redaction_type,
                    # Only the piece that still begins where the original span
                    # began carries its context note.
                    context=(
                        getattr(r, "context", None)
                        if start == r.start_char
                        else None
                    ),
                )
            )

    return sorted(pieces, key=lambda p: (p.start_char, p.end_char))
