"""
Deciding what a detected span is, and whose it is.

One place where three independent judgements meet:

* ``identity`` — is this name the case's data subject?
* ``blocks`` — what reads as one unit in this document?
* ``attribution`` — which person is this detail about?

and one answer comes out per span: its redaction type, whether it is born
decided, and the reason in words a reviewer can judge.

Three outcomes, and what separates them is how much confirmation each deserves:

* **Recognition.** The span is the data subject's name or date of birth as the
  case record holds it.  That is not an inference — it is the case owner's own
  entry recognised in the document — so it is born accepted under its own
  provenance.
* **Inference.** The span is a detail sitting in the same block as a name that
  matches the data subject.  The layout says it is theirs; nothing confirms it.
  Born **pending**, carrying its reasoning, for a human to confirm.
* **Everything else.** Third-party information, which is also where every
  uncertain answer lands.  Over-redaction is the failure direction this
  feature is required to take.

Operational markings are never reattributed, whatever block they sit in: what
makes them redactable is the marking, not whose record they appear in.
"""

from dataclasses import dataclass

from .attribution import attribute_spans
from .blocks import BlockKind, build_blocks
from .identity import IdentityMatch, match_person, matches_dob_text
from .models import Redaction

# Mapping from detector labels to Redaction types.
ENTITY_LABEL_TO_REDACTION_TYPE = {
    "DS_INFORMATION": Redaction.RedactionType.DS_INFORMATION,
    "THIRD_PARTY": Redaction.RedactionType.THIRD_PARTY_PII,
    "OPERATIONAL": Redaction.RedactionType.OPERATIONAL_DATA,
}

# How to name a block in a sentence a reviewer reads.
_BLOCK_PHRASES = {
    BlockKind.TABLE_ROW: "table row",
    BlockKind.PARAGRAPH: "paragraph",
    BlockKind.HEADING: "heading",
    BlockKind.LINE: "line",
}


@dataclass(frozen=True)
class SpanResolution:
    """What a span should become, and why."""

    redaction_type: str
    is_accepted: bool
    decided_by: str | None
    rationale: str | None = None

    @property
    def is_data_subject(self):
        return self.redaction_type == Redaction.RedactionType.DS_INFORMATION


def _matches_data_subject(text, case):
    """
    True if a detected span is unambiguously the data subject's own name or
    date of birth.

    Only an unambiguous identity match qualifies.  A span that merely overlaps
    the data subject's name — a shared surname, or a span that swallows a
    second person — comes back uncertain and is left as third-party, because
    resolving uncertainty toward the data subject is what discloses someone
    else's details.
    """
    ds_dob = getattr(case, "data_subject_dob", None)
    if matches_dob_text(text, ds_dob):
        return True

    return (
        match_person(
            text,
            ds_name=getattr(case, "data_subject_name", None),
            ds_dob=ds_dob,
        )
        is IdentityMatch.MATCH
    )


def _is_data_subject_person(person, case):
    """Whether an attributed person span is unambiguously the data subject."""
    return (
        match_person(
            person["text"],
            ds_name=getattr(case, "data_subject_name", None),
            ds_dob=getattr(case, "data_subject_dob", None),
        )
        is IdentityMatch.MATCH
    )


def _record_match_rationale(text, case):
    """Why a span was taken to be the data subject's own record entry."""
    if matches_dob_text(text, getattr(case, "data_subject_dob", None)):
        return "Matches the date of birth recorded on this case."
    return "Matches the name recorded on this case."


def _inference_rationale(person_text, block):
    """Why a detail was taken to be the data subject's."""
    phrase = _BLOCK_PHRASES.get(block.kind if block else None, "block")
    return (
        f'In the same {phrase} as "{person_text}", which matches the name '
        f"recorded on this case. Confirm this detail is the data subject's."
    )


def resolve_spans(
    spans,
    case,
    *,
    extracted_text=None,
    structure=None,
    tables=None,
    ruled_third_party=(),
):
    """
    Resolve detected spans against the case record and the document layout.

    Returns one ``SpanResolution`` per span, in the order the spans were given,
    so a caller can zip it against its own suggestion list.

    *ruled_third_party* is text a human has already ruled is a third party's
    somewhere in this case.  An attribution is a reading of a layout and can
    be wrong; when a reviewer corrects one, that correction has to stick, or
    the next document proposes the same thing again and they re-do the work on
    every document in the case.  A human decision outranks the layout, so such
    text is never proposed as the data subject's again — only inference is
    suppressed, never a match against the case record, which is not a guess.

    Attribution is skipped when there is no text to build blocks from, which
    leaves a caller that has only spans behaving exactly as it did before
    block attribution existed.
    """
    ruled_out = {text.casefold() for text in ruled_third_party if text}
    attributions_by_offset = {}
    if extracted_text:
        blocks = build_blocks(extracted_text, structure, tables)
        for attribution in attribute_spans(blocks, spans):
            # Offsets identify a span uniquely: deduplication has already
            # removed every overlapping span, so no two share a start and end.
            key = (
                attribution.span["start_char"],
                attribution.span["end_char"],
            )
            attributions_by_offset[key] = attribution

    resolutions = []
    for span in spans:
        mapped = ENTITY_LABEL_TO_REDACTION_TYPE.get(
            span["label"], Redaction.RedactionType.THIRD_PARTY_PII
        )

        if mapped == Redaction.RedactionType.OPERATIONAL_DATA:
            resolutions.append(
                SpanResolution(
                    redaction_type=mapped, is_accepted=False, decided_by=None
                )
            )
            continue

        if _matches_data_subject(span["text"], case):
            resolutions.append(
                SpanResolution(
                    redaction_type=Redaction.RedactionType.DS_INFORMATION,
                    is_accepted=True,
                    decided_by=Redaction.DecidedBy.DS_RECORD_MATCH,
                    rationale=_record_match_rationale(span["text"], case),
                )
            )
            continue

        attribution = attributions_by_offset.get(
            (span["start_char"], span["end_char"])
        )
        if (
            attribution is not None
            and attribution.is_resolved
            and span["text"].casefold() not in ruled_out
            and _is_data_subject_person(attribution.person, case)
        ):
            # The layout says this detail is the data subject's; nothing
            # confirms it. Pending, so a human decides before it is disclosed.
            resolutions.append(
                SpanResolution(
                    redaction_type=Redaction.RedactionType.DS_INFORMATION,
                    is_accepted=False,
                    decided_by=None,
                    rationale=_inference_rationale(
                        attribution.person["text"], attribution.block
                    ),
                )
            )
            continue

        resolutions.append(
            SpanResolution(
                redaction_type=mapped, is_accepted=False, decided_by=None
            )
        )

    return resolutions
