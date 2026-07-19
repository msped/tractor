"""
Disclosed-vs-current redaction diff.

Compares a case's latest disclosure snapshot — the "as-disclosed" record taken
on the most recent export — against the live redaction set, classifying every
difference as **added**, **removed**, or **modified**. Because a snapshot is a
complete capture keyed by redaction id (identity survives the snapshot round
trip), the diff is exact and near-free: rows are matched on id, so it reflects
every edit type a review can make — flip, add, delete, re-bound and re-type.
"""

from .models import Redaction

# The fields whose value, if it differs between the disclosed snapshot and the
# live redaction, constitutes a modification. Deliberately the human-meaningful
# edit surface: bounds (re-bound), text, type (re-type), the decision (flip)
# and any attached context. is_suggestion/source/created_at never change under
# review, so they are excluded from the comparison.
_DIFF_FIELDS = (
    "start_char",
    "end_char",
    "text",
    "redaction_type",
    "is_accepted",
    "decided_by",
    "justification",
    "context",
)


def _snapshot_entry(row, filenames):
    """Project a frozen snapshot row into a diff entry."""
    entry = {field: row.get(field) for field in _DIFF_FIELDS}
    entry["id"] = row["id"]
    entry["document_id"] = row["document_id"]
    entry["filename"] = filenames.get(row["document_id"])
    return entry


def _live_entry(redaction, filenames):
    """Project a live Redaction into a diff entry with the same shape."""
    context = getattr(redaction, "context", None)
    document_id = str(redaction.document_id)
    entry = {
        "start_char": redaction.start_char,
        "end_char": redaction.end_char,
        "text": redaction.text,
        "redaction_type": redaction.redaction_type,
        "is_accepted": redaction.is_accepted,
        "decided_by": redaction.decided_by,
        "justification": redaction.justification,
        "context": context.text if context is not None else None,
    }
    entry["id"] = str(redaction.id)
    entry["document_id"] = document_id
    entry["filename"] = filenames.get(document_id)
    return entry


def _export_summary(snapshot):
    """Identify the disclosure the baseline snapshot was frozen for."""
    export = snapshot.export
    if export is None:
        return None
    return {"sequence": export.sequence, "label": export.label}


def diff_disclosure(case):
    """
    Diff the case's latest disclosure snapshot against the live redaction set.

    Returns a dict of ``added`` / ``removed`` / ``modified`` entries (plus the
    baseline ``snapshot`` metadata and ``counts``), or ``None`` if the case has
    never been disclosed and so has no snapshot to diff against.

    - **added**: a live redaction with no counterpart in the snapshot.
    - **removed**: a snapshot redaction no longer present live.
    - **modified**: a redaction present in both whose bounds, text, type,
      decision or context changed; each carries a ``changes`` map of
      ``{field: {"from": ..., "to": ...}}``.
    """
    snapshot = (
        case.redaction_snapshots.select_related("export")
        .order_by("-created_at", "-id")
        .first()
    )
    if snapshot is None:
        return None

    filenames = {
        str(document_id): filename
        for document_id, filename in case.documents.values_list(
            "id", "filename"
        )
    }
    baseline = {row["id"]: row for row in snapshot.payload}

    live = (
        Redaction.objects.filter(document__case=case)
        .select_related("context")
        .order_by("document_id", "start_char", "id")
    )

    added = []
    modified = []
    seen = set()
    for redaction in live:
        redaction_id = str(redaction.id)
        seen.add(redaction_id)
        after = _live_entry(redaction, filenames)
        base = baseline.get(redaction_id)
        if base is None:
            added.append(after)
            continue
        changes = {
            field: {"from": base.get(field), "to": after[field]}
            for field in _DIFF_FIELDS
            if base.get(field) != after[field]
        }
        if changes:
            modified.append({**after, "changes": changes})

    removed = [
        _snapshot_entry(row, filenames)
        for redaction_id, row in baseline.items()
        if redaction_id not in seen
    ]

    return {
        "snapshot": {
            "id": str(snapshot.id),
            "created_at": snapshot.created_at.isoformat(),
            "export": _export_summary(snapshot),
        },
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
        },
        "added": added,
        "removed": removed,
        "modified": modified,
    }
