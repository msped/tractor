"""
Redaction snapshot module: freeze and restore the complete redaction set for
a case's documents.

Both operations are **system writes** — they are the mechanism the Internal
Review workflow uses to preserve and roll back disclosure state, and are
therefore exempt from the provenance lock (added in a later slice). Restore
never issues a decision-field ``update()``; it deletes the live rows and
recreates them from the frozen payload, so it does not travel through the
``RedactionQuerySet`` decision choke point at all.
"""

from django.db import transaction
from django.utils.dateparse import parse_datetime

from .models import Redaction, RedactionContext, RedactionSnapshot

# Every field of a Redaction that is captured, in the order they are
# reconstructed. `id`/`document_id` preserve identity across a round trip.
_SNAPSHOT_FIELDS = (
    "id",
    "document_id",
    "start_char",
    "end_char",
    "text",
    "justification",
    "redaction_type",
    "is_suggestion",
    "is_accepted",
    "decided_by",
    "source",
)


def _serialise_redaction(redaction):
    row = {field: getattr(redaction, field) for field in _SNAPSHOT_FIELDS}
    # UUIDs are not natively JSON-serialisable.
    row["id"] = str(redaction.id)
    row["document_id"] = str(redaction.document_id)
    row["created_at"] = redaction.created_at.isoformat()
    context = getattr(redaction, "context", None)
    row["context"] = context.text if context is not None else None
    return row


def snapshot_redactions(case):
    """
    Serialise every redaction (all fields + any RedactionContext) for the
    case's documents into a frozen RedactionSnapshot, and return it.
    """
    redactions = (
        Redaction.objects.filter(document__case=case)
        .select_related("context")
        .order_by("created_at", "id")
    )
    payload = [_serialise_redaction(r) for r in redactions]
    return RedactionSnapshot.objects.create(case=case, payload=payload)


@transaction.atomic
def restore_redactions(case, snapshot):
    """
    Replace the live redaction set for the case's documents with the set
    captured in ``snapshot``: rows added since the snapshot are deleted,
    deleted rows are recreated, and bounds/type/decision are reverted — so
    the live set becomes byte-for-byte identical to the snapshot, including
    RedactionContext.

    System write: exempt from the provenance lock.
    """
    # Cascades RedactionContext away with each redaction.
    Redaction.objects.filter(document__case=case).delete()

    redactions = []
    created_ats = []
    contexts = []
    for row in snapshot.payload:
        created_at = parse_datetime(row["created_at"])
        redaction = Redaction(
            created_at=created_at,
            **{field: row[field] for field in _SNAPSHOT_FIELDS},
        )
        redactions.append(redaction)
        created_ats.append(created_at)
        if row["context"] is not None:
            contexts.append(
                RedactionContext(redaction=redaction, text=row["context"])
            )

    Redaction.objects.bulk_create(redactions)
    # auto_now_add rewrites created_at on both the row and the in-memory
    # instance during bulk_create, so restore the frozen value and force it
    # back. created_at is not a decision field, so this update is permitted.
    for redaction, created_at in zip(redactions, created_ats, strict=True):
        redaction.created_at = created_at
    Redaction.objects.bulk_update(redactions, ["created_at"])
    RedactionContext.objects.bulk_create(contexts)
