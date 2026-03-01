"""
SpanCat-based entity extractor.

Runs a trained spaCy SpanCat model and maps doc.spans["sc"] entries
to the application's internal redaction label scheme (THIRD_PARTY / OPERATIONAL).
"""

_VALID_LABELS = {"THIRD_PARTY", "OPERATIONAL"}


def extract_with_spancat(nlp, text):
    """
    Run SpanCat prediction on *text* using the provided spaCy *nlp* pipeline.

    Returns a list of dicts with keys: text, label, start_char, end_char.
    Only spans with labels THIRD_PARTY or OPERATIONAL are returned.
    """
    doc = nlp(text)
    spans = doc.spans.get("sc", [])
    results = []
    for span in spans:
        if span.label_ not in _VALID_LABELS:
            continue
        results.append(
            {
                "text": span.text,
                "label": span.label_,
                "start_char": span.start_char,
                "end_char": span.end_char,
            }
        )
    return results
