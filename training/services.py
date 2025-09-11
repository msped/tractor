from .loader import SpacyModelManager
from spacy_layout import spaCyLayout


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
    extracted_text = doc.text

    if not extracted_text:
        raise ValueError("No text found in the document.")

    ner_doc = nlp(extracted_text)

    results = []
    for ent in ner_doc.ents:
        results.append({
            'text': ent.text,
            'label': ent.label_,
            'start_char': ent.start_char,
            'end_char': ent.end_char
        })

    return extracted_text, results
