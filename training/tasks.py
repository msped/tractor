import random
import subprocess
from pathlib import Path
from django.conf import settings
from docx import Document as DocxDocument
from django.utils import timezone
import spacy
from spacy.tokens import DocBin
from spacy.training import Example
from cases.models import Document, Redaction
from .models import (
    Model,
    TrainingDocument,
    TrainingRun,
    TrainingRunTrainingDoc,
    TrainingRunCaseDoc,
)

HIGHLIGHT_COLOR_TO_LABEL = {
    "BRIGHT_GREEN": "THIRD_PARTY_PII",
    "TURQUOISE": "OPERATIONAL_DATA",
}


def collect_training_data_detailed(source="both"):
    """
    Collects training data and tracks which docs were used.
    Returns (train_data, training_docs_used, case_docs_used).
    """
    train_data = []
    training_docs_used = []
    case_docs_used = []

    if source in ("training_docs", "both"):
        training_docs = TrainingDocument.objects.filter(processed=False)
        for tdoc in training_docs:
            try:
                doc = DocxDocument(tdoc.original_file.path)
                full_text = ""
                entities = []
                current_pos = 0

                for para in doc.paragraphs:
                    for run in para.runs:
                        run_text = run.text
                        start_char = current_pos
                        end_char = current_pos + len(run_text)
                        current_pos = end_char

                        if run.font.highlight_color:
                            color_name = str(run.font.highlight_color)
                            label = HIGHLIGHT_COLOR_TO_LABEL.get(color_name)
                            if label and run_text.strip():
                                entities.append((start_char, end_char, label))

                        full_text += run_text
                    full_text += "\n"  # Add newline after each paragraph
                    current_pos += 1

                if entities:
                    tdoc.extracted_text = full_text.strip()
                    tdoc.save(update_fields=['extracted_text'])
                    train_data.append(
                        (tdoc.extracted_text, {"entities": entities}))
                    training_docs_used.append(tdoc)
            except Exception as e:
                print(f"Could not process training doc {tdoc.name}: {e}")

    if source in ("redactions", "both"):
        completed_docs = Document.objects.filter(
            status=Document.Status.COMPLETED)
        for doc in completed_docs:
            text = doc.extracted_text
            if not text:
                continue

            entities = []
            for redaction in doc.redactions.filter(is_accepted=True).exclude(
                redaction_type=Redaction.RedactionType.DS_INFORMATION
            ):
                entities.append(
                    (
                        redaction.start_char,
                        redaction.end_char,
                        redaction.redaction_type,
                    )
                )
            if entities:
                train_data.append((text, {"entities": entities}))
                case_docs_used.append(doc)

    return train_data, training_docs_used, case_docs_used


def export_spacy_data(train_data, train_path, dev_path, split=0.8):
    """Export Django-collected data into spaCy DocBin format."""
    random.shuffle(train_data)
    split_point = int(len(train_data) * split)
    train_set, dev_set = train_data[:split_point], train_data[split_point:]

    nlp = spacy.blank("en")
    db_train = DocBin()
    db_dev = DocBin()

    for text, annotations in train_set:
        doc = nlp.make_doc(text)
        ents = []
        for start, end, label in annotations["entities"]:
            span = doc.char_span(start, end, label=label)
            if span:
                ents.append(span)
        doc.ents = ents
        db_train.add(doc)

    for text, annotations in dev_set:
        doc = nlp.make_doc(text)
        ents = []
        for start, end, label in annotations["entities"]:
            span = doc.char_span(start, end, label=label)
            if span:
                ents.append(span)
        doc.ents = ents
        db_dev.add(doc)

    db_train.to_disk(train_path)
    db_dev.to_disk(dev_path)


def train_model(source="both"):
    """
    Train a new spaCy model using the config-driven pipeline.
    """
    train_data, used_training_docs, used_case_docs = \
        collect_training_data_detailed(
            source)

    if len(train_data) < 25:
        print(
            f"Not enough training data ({len(train_data)} \
                examples). Aborting.")
        return

    # Export to corpora
    corpora_dir = Path(settings.BASE_DIR, "corpora")
    corpora_dir.mkdir(exist_ok=True)
    train_file = corpora_dir / "train.spacy"
    dev_file = corpora_dir / "dev.spacy"
    export_spacy_data(train_data, train_file, dev_file)

    # Prepare output dir
    model_name = f"model_{source}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = Path(settings.BASE_DIR, "nlp_models", model_name)

    try:
        active_model = Model.objects.get(is_active=True)
        base_model_path = active_model.path
    except Model.DoesNotExist:
        base_model_path = "en_core_web_lg"

    # Run spaCy train with subprocess
    config_path = Path(settings.BASE_DIR, "training", "config.cfg")
    cmd = [
        "python", "-m", "spacy", "train", str(config_path),
        "--output", str(output_dir),
        "--paths.train", str(train_file),
        "--paths.dev", str(dev_file),
        "--initialize.vectors", base_model_path
    ]
    subprocess.run(cmd, check=True)

    # Load best model for evaluation scores
    nlp = spacy.load(output_dir / "model-best")
    scores = nlp.evaluate([Example.from_dict(nlp.make_doc(t), ann)
                          for t, ann in train_data])

    # Register in DB
    new_model = Model.objects.create(
        name=model_name,
        path=str(output_dir / "model-best"),
        is_active=False,
        precision=scores.get("ents_p"),
        recall=scores.get("ents_r"),
        f1_score=scores.get("ents_f"),
    )

    # Create TrainingRun
    training_run = TrainingRun.objects.create(model=new_model, source=source)

    for tdoc in used_training_docs:
        TrainingRunTrainingDoc.objects.create(
            training_run=training_run, document=tdoc)
        tdoc.processed = True
        tdoc.save(update_fields=["processed"])

    for cdoc in used_case_docs:
        TrainingRunCaseDoc.objects.create(
            training_run=training_run, document=cdoc)

    print(
        f"Model trained and stored at {output_dir}, \
            DB updated, TrainingRun created.")
