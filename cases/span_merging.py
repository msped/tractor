"""
Single source of truth for span-merge semantics.

Policies:
  - review adjacency: same-type pairs whose character gap is at most
    REVIEW_GAP_THRESHOLD, emitted as status-independent MergePairs the
    review UI activates per section (phase 1: verbatim the rule the
    frontend previously implemented in mergeRedactionSpans.js).
  - export removal merge: type-agnostic collapse of spans separated only
    by whitespace/separator characters (moved verbatim from services.py,
    together with the '#' prefix absorption).
"""

from dataclasses import dataclass

REVIEW_GAP_THRESHOLD = 2

# Characters that count as "nothing" between two adjacent redactions and
# cause them to be merged into a single [...].  Whitespace plus common
# punctuation separators (commas, colons, semicolons, hyphens, slashes…)
# so that e.g. "[name], [address]" becomes a single [...].
REMOVAL_GAP_CHARS = frozenset(" \t\n\r\f\v,.:;-/&|()'\"")

# Prefix symbols absorbed into a span when they immediately precede it
# (handles documents processed before the extraction-layer '#' fix).
ABSORBED_PREFIX_CHARS = frozenset("#")


@dataclass(frozen=True)
class MergePair:
    """A status-independent review adjacency between two redactions.

    The client activates a pair iff both endpoints share a review section
    AND no blocker is in that section — reproducing per-section merging,
    including the case where a different-type span between two same-type
    spans breaks their merge only while it shares their section.
    """

    a: str  # redaction id (earlier span)
    b: str  # redaction id (later span)
    type: str  # redaction_type both had when computed
    joiner: str  # text to place between constituents when merged
    blockers: tuple  # ids of redactions sorted strictly between a and b


def compute_review_merge_pairs(redactions):
    """Emit every ordered same-type pair within the review gap rule.

    Status-independent: depends only on span positions and types, so the
    client can re-partition locally on every accept/reject without a
    round-trip.
    """
    spans = sorted(redactions, key=lambda r: (r.start_char, r.end_char))
    pairs = []
    for i, a in enumerate(spans):
        for b in spans[i + 1 :]:
            gap = b.start_char - a.end_char
            if gap > REVIEW_GAP_THRESHOLD:
                # start_char is non-decreasing, so the gap to every later
                # span is at least this one — no more pairs for `a`.
                break
            if b.redaction_type != a.redaction_type:
                continue
            blockers = tuple(
                str(x.id)
                for x in spans
                if (a.start_char, a.end_char) < (x.start_char, x.end_char)
                and (x.start_char, x.end_char) < (b.start_char, b.end_char)
            )
            pairs.append(
                MergePair(
                    a=str(a.id),
                    b=str(b.id),
                    type=a.redaction_type,
                    joiner=" " if gap > 0 else "",
                    blockers=blockers,
                )
            )
    return pairs


def serialize_merge_structure(redactions):
    """The additive `merge_structure` API block for a document's redactions."""
    return {
        "version": 1,
        "pairs": [
            {
                "a": p.a,
                "b": p.b,
                "type": p.type,
                "joiner": p.joiner,
                "blockers": list(p.blockers),
            }
            for p in compute_review_merge_pairs(redactions)
        ],
    }


def is_separator_gap(text):
    return bool(text) and all(c in REMOVAL_GAP_CHARS for c in text)


def absorb_prefix_symbols(full_text, start, floor):
    """Expand `start` backwards over prefix symbols (e.g. '#') down to `floor`."""
    while start > floor and full_text[start - 1] in ABSORBED_PREFIX_CHARS:
        start -= 1
    return start


def merge_spans_for_removal(full_text, seg_start, seg_end, sorted_redactions):
    """Collapse overlapping/adjacent redaction spans into merged (start, end) pairs.

    Two spans are merged when the gap between them is empty, pure whitespace,
    or consists solely of punctuation/separator characters (so that constructs
    like "[name], [address]" collapse to a single [...]).
    """
    spans = []
    for r in sorted_redactions:
        if r.end_char <= seg_start or r.start_char >= seg_end:
            continue
        r_start = max(r.start_char, seg_start)
        r_end = min(r.end_char, seg_end)
        r_start = absorb_prefix_symbols(full_text, r_start, seg_start)
        if not spans:
            spans.append([r_start, r_end])
        else:
            gap = full_text[spans[-1][1] : r_start]
            if (
                r_start <= spans[-1][1]
                or not gap.strip()
                or is_separator_gap(gap)
            ):
                spans[-1][1] = max(spans[-1][1], r_end)
            else:
                spans.append([r_start, r_end])
    return spans
