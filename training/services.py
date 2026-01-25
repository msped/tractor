from docling_core.types.doc import TableItem
from spacy_layout import spaCyLayout

from .loader import SpacyModelManager


def extract_entities_from_text(path):
    """
    Processes text with the currently active spaCy model and
    returns extracted entities.
    """
    nlp = SpacyModelManager.get_instance().get_model()
    if not nlp:
        raise ValueError("No active spaCy model found.")
    layout = spaCyLayout(nlp)
    doc = layout(path)

    # Build extracted text including tables
    text_parts = []

    # Get main document text
    if doc.text:
        text_parts.append(doc.text)

    # Extract tables from the docling document layout
    if hasattr(doc._, "layout") and doc._.layout is not None:
        docling_doc = doc._.layout
        for item, _level in docling_doc.iterate_items():
            if isinstance(item, TableItem):
                table_text = item.export_to_markdown()
                if table_text:
                    text_parts.append(f"\n\n{table_text}\n")

    extracted_text = "".join(text_parts)

    if not extracted_text:
        raise ValueError("No text found in the document.")

    ner_doc = nlp(extracted_text)

    results = []
    for ent in ner_doc.ents:
        results.append({"text": ent.text, "label": ent.label_, "start_char": ent.start_char, "end_char": ent.end_char})

    return extracted_text, results
