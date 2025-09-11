import spacy
from spacy.training import Example
import random
from pathlib import Path
from django.conf import settings
from django.utils import timezone

from cases.models import Document, Redaction
from .models import Model

# This requires further testing and validation before being #
# used in production and possibly changing to spacy train config #


def train_new_model():
    """
    A task to train a new spaCy model based on accepted redactions.
    """
    # 1. Gather all completed documents with accepted redactions
    completed_docs = Document.objects.filter(status=Document.Status.COMPLETED)
    train_data = []
    for doc in completed_docs:
        text = doc.extracted_text
        if not text:
            continue

        entities = []
        for redaction in doc.redactions.filter(
            is_accepted=True
        ).exclude(redaction_type=Redaction.RedactionType.DS_INFORMATION):
            # format is (start_char, end_char, LABEL)
            entities.append(
                (
                    redaction.start_char,
                    redaction.end_char,
                    redaction.redaction_type
                )
            )

        if entities:
            train_data.append((text, {"entities": entities}))

    if len(train_data) < 25:
        print(
            f"Not enough training data ({len(train_data)} examples). "
            "A minimum of 25 is required for training and evaluation. "
            "Aborting."
        )
        return

    # 2. Split data into training and evaluation sets (80/20 split)
    random.shuffle(train_data)
    split_point = int(len(train_data) * 0.8)
    train_set = train_data[:split_point]
    dev_set = train_data[split_point:]
    print(
        f"Data split: {len(train_set)} training, \
            {len(dev_set)} evaluation examples.")

    # 3. Train a new spaCy model
    nlp = spacy.blank("en")
    ner = nlp.add_pipe("ner", last=True)

    # Add all unique labels to the NER pipe
    for _, annotations in train_set + dev_set:
        for ent in annotations.get("entities"):
            ner.add_label(ent[2])

    # Disable other pipes during training
    with nlp.select_pipes(disable=[p for p in nlp.pipe_names if p != "ner"]):
        optimizer = nlp.begin_training()
        for itn in range(10):  # Number of training iterations
            random.shuffle(train_set)
            losses = {}
            for text, annotations in train_set:
                example = Example.from_dict(nlp.make_doc(text), annotations)
                nlp.update([example], drop=0.5, sgd=optimizer, losses=losses)
            print(f"Losses at iteration {itn}: {losses}")

    # 4. Evaluate the model on the development set
    scores = {}
    if dev_set:
        print("Evaluating model...")
        dev_examples = []
        for text, annotations in dev_set:
            doc = nlp.make_doc(text)
            dev_examples.append(Example.from_dict(doc, annotations))

        scores = nlp.evaluate(dev_examples)
        print("Evaluation scores:", scores)

    # 5. Save the new model to a versioned directory
    model_name = f"model_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = Path(settings.BASE_DIR, "nlp_models", model_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    nlp.to_disk(output_dir)
    print(f"Saved model to {output_dir}")

    # 6. Create a new Model record in the database with evaluation scores
    Model.objects.create(
        name=model_name,
        path=str(output_dir),
        is_active=False,
        precision=scores.get("ents_p"),
        recall=scores.get("ents_r"),
        f1_score=scores.get("ents_f")
    )
