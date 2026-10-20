"""
Attributing a detail to the person it describes.

A detected phone number, address or email is only meaningful once you know
whose it is.  This module answers that one question: for each detail span,
which person span is it about?  The answer comes from document layout — a
detail and a name in the same block belong together — and it is allowed to be
"don't know".

Pure logic over spans and blocks: no ORM, no document, no I/O.

The rule is deliberately timid.  A block containing exactly one person
attributes its details to that person; a block containing two people, or none,
resolves to nothing.  Guessing between two candidates would eventually
attribute a third party's phone number to the data subject and disclose it,
so there is no tie-break and no nearest-name heuristic.  An unresolved detail
is treated as a third party's, which over-redacts — the direction this feature
is required to fail in.
"""

from dataclasses import dataclass

from .blocks import block_for_span

# Detector labels that mean "this span is a person".  Each detector names the
# type in its own vocabulary: GLiNER reports its raw prompt label, Presidio its
# recognizer entity.  Compared casefolded with separators normalised, so
# "person name", "PERSON_NAME" and "PERSON" all read alike.
_PERSON_ENTITY_TYPES = frozenset({"person name", "person"})

# Labels that mean "this span is a personal detail that belongs to somebody".
#
# A positive list, not "everything that isn't a person", and that is a safety
# property rather than tidiness.  Attribution feeds the DS_INFORMATION label,
# which is the *disclosed* category — so attributing a third party's detail to
# the data subject hands it to the requester.  A span of unrecognised type
# (SpanCat and Gemma report none at all, and SpanCat is trained largely on
# names) must therefore never be attributed: an unknown span stays third-party
# and stays redacted.
#
# Deliberately excludes "location" and "organisation".  Neither is a detail
# *of* a person in the way a phone number or address is, and a town or employer
# standing near the data subject's name is not thereby theirs to disclose.
_DETAIL_ENTITY_TYPES = frozenset(
    {
        "address",
        "date of birth",
        "phone number",
        "email address",
        "uk nhs",
        "uk postcode",
        "uk ni number",
    }
)

# Spans whose redactability comes from the marking rather than from whose
# record they sit in.  Never attributed: an operational reference inside the
# data subject's own block is still operational.
_OPERATIONAL_LABEL = "OPERATIONAL"


def _normalised_entity_type(entity_type):
    if not entity_type:
        return ""
    return entity_type.replace("_", " ").strip().casefold()


def is_person_span(span):
    """
    True when a span is a person's name.

    Decided from ``entity_type`` — the detector's own fine-grained label —
    because every detector collapses its output to THIRD_PARTY or OPERATIONAL
    for the redaction layer, and that coarse label cannot tell a name from a
    detail about the person named.

    A span with no ``entity_type`` (SpanCat, Gemma) is not treated as a person.
    Neither detector reports a fine-grained type, so there is nothing to read;
    the consequence is that a detail whose only nearby name came from SpanCat
    stays unattributed rather than being attached to a name nobody confirmed.
    """
    entity_type = _normalised_entity_type(span.get("entity_type"))
    return entity_type in _PERSON_ENTITY_TYPES


def is_attributable(span):
    """
    True when a span is a personal detail that could belong to someone.

    Requires a recognised detail type.  Person names are excluded — a name is
    matched against the case record by the identity matcher, not attributed to
    itself — and so is anything whose type is unrecognised or absent, because
    attribution grants disclosure and an unidentified span has not earned it.
    Operational spans are excluded outright whatever their type.
    """
    if span.get("label") == _OPERATIONAL_LABEL:
        return False
    return (
        _normalised_entity_type(span.get("entity_type"))
        in _DETAIL_ENTITY_TYPES
    )


@dataclass(frozen=True)
class Attribution:
    """
    One detail span and the person it was attributed to.

    ``person`` is None when attribution found no single answer — the detail sat
    in a block with no person, with more than one person, or in no block at
    all.  Callers must resolve that toward redaction, never toward disclosure.
    """

    span: dict
    person: dict | None
    block: object | None

    @property
    def is_resolved(self):
        return self.person is not None


def _people_in_block(blocks, spans):
    """Map each block to the person spans wholly inside it."""
    people = {}
    for span in spans:
        if not is_person_span(span):
            continue
        block = block_for_span(blocks, span["start_char"], span["end_char"])
        if block is None:
            continue
        people.setdefault(block, []).append(span)
    return people


def attribute_spans(blocks, spans):
    """
    Attribute every attributable span in *spans* to a person in its block.

    Returns an ``Attribution`` per attributable span, in the order the spans
    were given.  Person spans, operational spans and spans of unrecognised
    type produce no entry at all — they are not details about anyone, and the
    caller leaves them classified as they came.
    """
    people_by_block = _people_in_block(blocks, spans)

    attributions = []
    for span in spans:
        if not is_attributable(span):
            continue

        block = block_for_span(blocks, span["start_char"], span["end_char"])
        candidates = people_by_block.get(block, []) if block else []
        # Exactly one person, or no answer.  Two people in a block is the case
        # this module exists to refuse.
        person = candidates[0] if len(candidates) == 1 else None
        attributions.append(Attribution(span=span, person=person, block=block))

    return attributions
