// A suggestion's review state comes from its provenance, as on the backend
// (`pending()` is `decided_by__isnull=True`); a reject carries no reason.
export const isPendingSuggestion = (r) => r.is_suggestion && !r.decided_by;

export const isRejectedSuggestion = (r) => r.is_suggestion && !!r.decided_by && !r.is_accepted;

// The write that puts a redaction back to the decision captured in `snap`,
// for undo. A non-accept only counts as a reject with the flag; without it the
// server withdraws the decision to pending.
export const decisionWriteFor = (snap) => ({
    is_accepted: snap.is_accepted,
    rejected: !snap.is_accepted && !!snap.decided_by,
    exemption: snap.exemption ?? null,
});
