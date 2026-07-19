"""
DS_INFO propagation: text a reviewer marked as data-subject information in
one document is auto-accepted wherever it appears elsewhere in the case.

Plan/apply split: planning reads and decides (no writes), applying is the
sole writer of propagation acceptance state.
"""

import logging
import re
from dataclasses import dataclass, field

import inflect
from django.db import transaction
from django.db.models import Q

from .models import Document, Redaction

logger = logging.getLogger(__name__)

# Above this many matched positions in a single document, fetch all of the
# document's redactions instead of building an OR'd positional query.
_POSITIONAL_FETCH_MAX = 100


@dataclass(frozen=True)
class TermPattern:
    """A search term expanded to its compiled whole-word variation regex."""

    term: str
    regex: re.Pattern


def build_term_patterns(terms):
    """
    Expand each non-blank term to its plural/singular variations and compile
    a whole-word, case-insensitive regex with variations sorted longest-first
    (so e.g. "data subjects" matches before "data").
    """
    patterns = []
    p = inflect.engine()
    for term in terms:
        if not term or not term.strip():
            continue

        variations = {term}
        plural_form = p.plural(term)
        if plural_form and plural_form != term:
            variations.add(plural_form)
        singular_form = p.singular_noun(term)
        if singular_form and singular_form != term:
            variations.add(singular_form)

        sorted_variations = sorted(variations, key=len, reverse=True)
        # Lookarounds instead of \b so terms edged with punctuation
        # (e.g. "#071234", "O'Brien (Jr.)") still match whole-word.
        pattern = (
            r"(?<!\w)("
            + "|".join(re.escape(v) for v in sorted_variations)
            + r")(?!\w)"
        )
        patterns.append(
            TermPattern(term=term, regex=re.compile(pattern, re.IGNORECASE))
        )
    return patterns


@dataclass
class PropagationPlan:
    """The resolved outcome of scanning one document for DS_INFO terms."""

    document: Document
    to_create: list = field(default_factory=list)
    to_accept: list = field(default_factory=list)
    to_upgrade: list = field(default_factory=list)
    ids_to_delete: list = field(default_factory=list)

    @property
    def is_empty(self):
        return not (
            self.to_create
            or self.to_accept
            or self.to_upgrade
            or self.ids_to_delete
        )


def _find_matches(document, patterns):
    """
    Scan the document text with each pattern in order; earlier terms claim
    overlapping positions. Returns {(start, end): matched_text}.
    """
    matches = {}
    for term_pattern in patterns:
        for match in term_pattern.regex.finditer(document.extracted_text):
            pos = match.span()
            if pos not in matches:
                matches[pos] = match.group(0)
    return matches


def _fetch_existing_by_position(document, positions):
    """
    Fetch only the document's redactions at the matched positions (covered
    by redaction_doc_pos_idx), grouped by (start_char, end_char).
    """
    if len(positions) > _POSITIONAL_FETCH_MAX:
        existing = document.redactions.all()
    else:
        position_q = Q()
        for start, end in positions:
            position_q |= Q(start_char=start, end_char=end)
        existing = document.redactions.filter(position_q)

    by_position = {}
    for r in existing:
        by_position.setdefault((r.start_char, r.end_char), []).append(r)
    return by_position


def plan_document(document, patterns):
    """
    Scan one document for all terms and resolve each matched position:
    existing DS_INFO -> ensure accepted, delete duplicates; other type at
    the same span -> upgrade to DS_INFO; nothing -> create born-accepted.
    Read-only: performs no redaction queries when nothing matches.
    """
    plan = PropagationPlan(document=document)

    if not document.extracted_text:
        return plan

    matches = _find_matches(document, patterns)
    if not matches:
        return plan

    existing_by_position = _fetch_existing_by_position(
        document, matches.keys()
    )

    for (start, end), text in matches.items():
        existing = existing_by_position.get((start, end), [])
        ds_info = [
            r
            for r in existing
            if r.redaction_type == Redaction.RedactionType.DS_INFORMATION
        ]
        others = [
            r
            for r in existing
            if r.redaction_type != Redaction.RedactionType.DS_INFORMATION
        ]

        if ds_info:
            primary = ds_info[0]
            if not primary.is_accepted:
                plan.to_accept.append(primary)
            plan.ids_to_delete.extend(r.id for r in ds_info[1:])
            plan.ids_to_delete.extend(r.id for r in others)
        elif others:
            plan.to_upgrade.append(others[0])
            plan.ids_to_delete.extend(r.id for r in others[1:])
        else:
            plan.to_create.append(
                Redaction(
                    document=document,
                    start_char=start,
                    end_char=end,
                    text=text,
                    redaction_type=Redaction.RedactionType.DS_INFORMATION,
                    is_suggestion=True,
                    is_accepted=True,
                    decided_by=Redaction.DecidedBy.DS_INFO_PROPAGATION,
                )
            )

    return plan


def apply_plan(plan):
    """
    Persist a plan atomically (one transaction per document): one delete +
    one bulk_create + one bulk_update, skipping no-ops. Complete no-op —
    not even a transaction — when the plan is empty.

    The sole writer of propagation acceptance state.
    """
    if plan.is_empty:
        return

    for redaction in plan.to_upgrade:
        redaction.redaction_type = Redaction.RedactionType.DS_INFORMATION
        redaction.is_suggestion = True

    with transaction.atomic():
        if plan.ids_to_delete:
            Redaction.objects.filter(id__in=plan.ids_to_delete).delete()
        if plan.to_create:
            Redaction.objects.bulk_create(plan.to_create)
        if plan.to_upgrade:
            Redaction.objects.bulk_update(
                plan.to_upgrade, ["redaction_type", "is_suggestion"]
            )
        ids_to_accept = [r.id for r in plan.to_accept + plan.to_upgrade]
        if ids_to_accept:
            Redaction.objects.filter(id__in=ids_to_accept).accept(
                by=Redaction.DecidedBy.DS_INFO_PROPAGATION
            )


def propagate_terms_to_document(document, terms):
    """Cold path: scan one document for all of the given DS_INFO terms."""
    patterns = build_term_patterns(terms)
    if not patterns:
        return
    apply_plan(plan_document(document, patterns))


def _other_reviewable_documents(source_document):
    """Every reviewable document in the case except the source itself."""
    return Document.objects.filter(
        case=source_document.case,
        status__in=[
            Document.Status.READY_FOR_REVIEW,
            Document.Status.COMPLETED,
        ],
    ).exclude(id=source_document.id)


def preview_propagation(source_redaction):
    """
    Plan (but do not apply) propagation of one redaction's term across the
    case. Returns the non-empty :class:`PropagationPlan` for each other
    document that would be touched — read-only, so a reviewer can confirm the
    affected documents before any write happens.
    """
    patterns = build_term_patterns([source_redaction.text])
    if not patterns:
        return []

    plans = []
    for document in _other_reviewable_documents(source_redaction.document):
        plan = plan_document(document, patterns)
        if not plan.is_empty:
            plans.append(plan)
    return plans


def summarize_propagation(source_redaction):
    """
    Build the affected-documents summary a reviewer confirms against.

    Each entry counts the positions that would be created, accepted or
    upgraded in that document (duplicate cleanup is not surfaced).
    """
    affected = []
    total = 0
    for plan in preview_propagation(source_redaction):
        count = (
            len(plan.to_create) + len(plan.to_accept) + len(plan.to_upgrade)
        )
        total += count
        affected.append(
            {
                "document_id": str(plan.document.id),
                "filename": plan.document.filename,
                "match_count": count,
            }
        )
    return {
        "term": source_redaction.text,
        "affected_documents": affected,
        "total_matches": total,
    }


def propagate_term_across_case(source_redaction):
    """Hot path: scan all other reviewable case documents for one term."""
    patterns = build_term_patterns([source_redaction.text])
    if not patterns:
        return

    logger.info(
        "Searching for variations of '%s' in other documents for case %s.",
        source_redaction.text,
        source_redaction.document.case.case_reference,
    )

    for document in _other_reviewable_documents(source_redaction.document):
        apply_plan(plan_document(document, patterns))
