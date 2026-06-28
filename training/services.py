import logging
import re

from .extraction import _extract_text_from_pdf, extract_document_structure
from .pipeline import build_default_pipeline

logger = logging.getLogger(__name__)

_PREFIX_CHARS = {"#"}


def _expand_prefix_symbols(entities, text):
    """Extend entity start positions to include an immediately preceding '#' or similar symbol."""
    for ent in entities:
        start = ent["start_char"]
        if start > 0 and text[start - 1] in _PREFIX_CHARS:
            ent["start_char"] = start - 1
            ent["text"] = text[ent["start_char"] : ent["end_char"]]
    return entities


def extract_entities_from_text(
    path, data_subject_name=None, data_subject_dob=None, *, pipeline=None
):
    """Run the full NLP pipeline (SpanCat → GLiNER → Presidio → Gemma) on a document file.

    Pass a custom ExtractionPipeline via ``pipeline`` to override the default
    (useful in tests — no model manager mocking required).

    Returns:
        Tuple of (extracted_text, entity_suggestions, tables, spacy_model_entry).
    """
    if pipeline is None:
        pipeline = build_default_pipeline(data_subject_name, data_subject_dob)

    if path.lower().endswith(".txt"):
        with open(path, encoding="utf-8") as f:
            ner_text = f.read()
        if not ner_text.strip():
            return "", [], [], None
        combined = pipeline.run(ner_text)
        combined = _expand_prefix_symbols(combined, ner_text)
        return ner_text, combined, [], None

    # Try structure extraction for DOCX files first
    structure_result = extract_document_structure(path)

    if structure_result[0] is not None:
        # DOCX file - use python-docx extraction
        structure, tables, ner_text = structure_result

        if not ner_text or not ner_text.strip():
            return "", [], tables, structure
    else:
        # Fallback to pypdf for non-DOCX files (PDF, etc.)
        ner_text = _extract_text_from_pdf(path)
        ner_text = re.sub(r"\n{3,}", "\n\n", ner_text)
        structure = None
        tables = []

        if not ner_text.strip():
            return "", [], [], None

    combined = pipeline.run(ner_text)
    combined = _expand_prefix_symbols(combined, ner_text)

    return ner_text, combined, tables, structure
