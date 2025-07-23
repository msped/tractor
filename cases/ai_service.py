import spacy
from spacy_layout import spaCyLayout

nlp = spacy.load("en_core_web_lg")
layout = spaCyLayout(nlp)


def extract_entities_from_text(path):
    """
    Processes text with spaCy and returns a list of found entities.
    """
    doc = layout(path)
    extracted_text = doc.text
    doc = nlp(doc)
    if not extracted_text:
        raise ValueError("No text found in the document.")
    results = []
    for ent in doc.ents:
        results.append({
            'text': ent.text,
            'label': ent.label_,
            'start_char': ent.start_char,
            'end_char': ent.end_char
        })
    return extracted_text, results
