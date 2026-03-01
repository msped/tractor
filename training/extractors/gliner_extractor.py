"""
GLiNER-based entity extractor.

Maps GLiNER label predictions to the THIRD_PARTY redaction label.
OPERATIONAL entities are handled by SpanCat (trained) and Presidio (structured patterns).
"""

GLINER_LABELS = [
    "person name",
    "organisation",
    "location",
    "date of birth",
    "address",
]

_LABEL_TO_REDACTION_TYPE = {
    "person name": "THIRD_PARTY",
    "organisation": "THIRD_PARTY",
    "location": "THIRD_PARTY",
    "date of birth": "THIRD_PARTY",
    "address": "THIRD_PARTY",
}

# GLiNER's underlying transformer tokenises to ~384 subword tokens max.
# ~1500 characters is a safe upper bound before truncation warnings appear.
_MAX_CHUNK_CHARS = 1500


def _chunk_text(text):
    """
    Split *text* into ``(chunk, start_offset)`` pairs that each fit within
    GLiNER's token limit (~384 subword tokens ≈ 1500 characters).

    Prefers breaking at newline boundaries, then at word (space) boundaries,
    so that entity offsets remain correct when re-added to *start_offset*.
    """
    if len(text) <= _MAX_CHUNK_CHARS:
        return [(text, 0)]

    chunks = []
    pos = 0
    while pos < len(text):
        end = min(pos + _MAX_CHUNK_CHARS, len(text))
        if end < len(text):
            # Prefer a newline break to keep paragraphs intact
            newline = text.rfind("\n", pos, end)
            if newline > pos:
                end = newline + 1
            else:
                # Fall back to a word boundary
                space = text.rfind(" ", pos, end)
                if space > pos:
                    end = space + 1
        chunks.append((text[pos:end], pos))
        pos = end
    return chunks


def extract_with_gliner(model, text):
    """
    Run GLiNER prediction on *text* using the provided *model*.

    Long texts are split into chunks to avoid the model's token limit.
    Returns a list of dicts with keys: text, label, start_char, end_char.
    ``label`` is the application-level redaction type (THIRD_PARTY or OPERATIONAL).
    """
    results = []
    for chunk, offset in _chunk_text(text):
        raw = model.predict_entities(chunk, GLINER_LABELS, flat_ner=True, threshold=0.35)
        for ent in raw:
            redaction_label = _LABEL_TO_REDACTION_TYPE.get(ent["label"])
            if redaction_label is None:
                continue
            results.append(
                {
                    "text": ent["text"],
                    "label": redaction_label,
                    "start_char": ent["start"] + offset,
                    "end_char": ent["end"] + offset,
                }
            )
    return results
