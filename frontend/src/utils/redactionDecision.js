// A suggestion's review state comes from its provenance, as on the backend
// (`pending()` is `decided_by__isnull=True`). A rejection can carry no
// justification, so the justification text says nothing about the state.
export const isPendingSuggestion = (r) => r.is_suggestion && !r.decided_by;

export const isRejectedSuggestion = (r) => r.is_suggestion && !!r.decided_by && !r.is_accepted;
