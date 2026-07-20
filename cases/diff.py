"""
Redaction diffs between disclosure states.

Two views are offered, both built on the same id-matched comparison:

- :func:`diff_disclosure` diffs the case's *latest* disclosure snapshot against
  the current live redaction set — "what has changed since the last
  disclosure", the working preview shown while a review is open.
- :func:`diff_export` diffs one preserved disclosure against the one before it
  — "what that review changed", the historical record for a past disclosure.

Because a snapshot is a complete capture keyed by redaction id (identity
survives the snapshot round trip), each diff is exact and near-free: rows are
matched on id, so it reflects every edit type a review can make — flip, add,
delete, re-bound and re-type.
"""

from .models import Redaction, RedactionSnapshot

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


def _classify(before_by_id, after_by_id):
    """
    Compare two id-keyed maps of diff entries.

    Returns ``(added, removed, modified)`` where *added* is present only in
    ``after``, *removed* only in ``before``, and *modified* is present in both
    with at least one :data:`_DIFF_FIELDS` value changed — each modified entry
    carrying a ``changes`` map of ``{field: {"from": ..., "to": ...}}``.
    """
    added = []
    modified = []
    for redaction_id, after in after_by_id.items():
        base = before_by_id.get(redaction_id)
        if base is None:
            added.append(after)
            continue
        changes = {
            field: {"from": base.get(field), "to": after.get(field)}
            for field in _DIFF_FIELDS
            if base.get(field) != after.get(field)
        }
        if changes:
            modified.append({**after, "changes": changes})

    removed = [
        before
        for redaction_id, before in before_by_id.items()
        if redaction_id not in after_by_id
    ]
    return added, removed, modified


def _filenames_for(case):
    return {
        str(document_id): filename
        for document_id, filename in case.documents.values_list(
            "id", "filename"
        )
    }


def _counts(added, removed, modified):
    return {
        "added": len(added),
        "removed": len(removed),
        "modified": len(modified),
    }


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

    filenames = _filenames_for(case)
    before_by_id = {
        row["id"]: _snapshot_entry(row, filenames) for row in snapshot.payload
    }

    live = (
        Redaction.objects.filter(document__case=case)
        .select_related("context")
        .order_by("document_id", "start_char", "id")
    )
    after_by_id = {
        str(redaction.id): _live_entry(redaction, filenames)
        for redaction in live
    }

    added, removed, modified = _classify(before_by_id, after_by_id)

    return {
        "snapshot": {
            "id": str(snapshot.id),
            "created_at": snapshot.created_at.isoformat(),
            "export": _export_summary(snapshot),
        },
        "counts": _counts(added, removed, modified),
        "added": added,
        "removed": removed,
        "modified": modified,
    }


def diff_export(export):
    """
    Diff a preserved disclosure ``export`` against the disclosure before it —
    the changes that produced this disclosure.

    Returns a dict of ``added`` / ``removed`` / ``modified`` entries plus
    ``counts`` and the ``base``/``target`` disclosures being compared. The first
    disclosure has no predecessor, so its diff is a ``baseline`` marker with
    empty change lists. Returns ``None`` when the export itself has no snapshot
    (a legacy disclosure predating snapshotting) and so cannot be diffed.
    """
    target_snapshot = RedactionSnapshot.objects.filter(export=export).first()
    if target_snapshot is None:
        return None

    case = export.case
    target = {
        "sequence": export.sequence,
        "label": export.label,
        "created_at": export.created_at.isoformat(),
    }

    previous_snapshot = (
        RedactionSnapshot.objects.filter(
            export__case=case, export__sequence__lt=export.sequence
        )
        .select_related("export")
        .order_by("-export__sequence")
        .first()
    )
    if previous_snapshot is None:
        return {
            "baseline": True,
            "base": None,
            "target": target,
            "counts": _counts([], [], []),
            "added": [],
            "removed": [],
            "modified": [],
        }

    filenames = _filenames_for(case)
    before_by_id = {
        row["id"]: _snapshot_entry(row, filenames)
        for row in previous_snapshot.payload
    }
    after_by_id = {
        row["id"]: _snapshot_entry(row, filenames)
        for row in target_snapshot.payload
    }

    added, removed, modified = _classify(before_by_id, after_by_id)

    return {
        "baseline": False,
        "base": _export_summary(previous_snapshot),
        "target": target,
        "counts": _counts(added, removed, modified),
        "added": added,
        "removed": removed,
        "modified": modified,
    }
