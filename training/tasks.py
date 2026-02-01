import random
import shutil
import subprocess
from pathlib import Path

import spacy
from django.conf import settings
from django.utils import timezone
from django_q.models import Task
from docx import Document as DocxDocument
from spacy.tokens import DocBin
from spacy.training import Example

from cases.models import Document, Redaction

from .models import (
    Model,
    TrainingDocument,
    TrainingRun,
    TrainingRunCaseDoc,
    TrainingRunTrainingDoc,
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
        # Get ALL training documents for cumulative training
        training_docs = TrainingDocument.objects.all()
        for tdoc in training_docs:
            try:
                doc = DocxDocument(tdoc.original_file.path)
                full_text = ""
                entities = []
                current_pos = 0

                # Track current highlighted section for merging adjacent runs
                current_entity_start = None
                current_entity_end = None
                current_entity_label = None

                def close_current_entity(entities_list, text):
                    """Close the current entity if one is open and has content."""
                    nonlocal current_entity_start, current_entity_end, current_entity_label
                    if current_entity_start is not None and current_entity_label is not None:
                        # Check if the entity text has actual content (not just whitespace)
                        entity_text = text[current_entity_start:current_entity_end]
                        stripped_text = entity_text.strip()
                        if stripped_text:
                            # Adjust boundaries to exclude leading/trailing whitespace
                            # This ensures alignment with spaCy token boundaries
                            leading_ws = len(entity_text) - len(entity_text.lstrip())
                            trailing_ws = len(entity_text) - len(entity_text.rstrip())
                            adjusted_start = current_entity_start + leading_ws
                            adjusted_end = current_entity_end - trailing_ws
                            entities_list.append((adjusted_start, adjusted_end, current_entity_label))
                    current_entity_start = None
                    current_entity_end = None
                    current_entity_label = None

                for para in doc.paragraphs:
                    for run in para.runs:
                        run_text = run.text
                        start_char = current_pos
                        end_char = current_pos + len(run_text)

                        # Determine the label for this run
                        run_label = None
                        if run.font.highlight_color:
                            color_enum_member = run.font.highlight_color
                            color_name = color_enum_member.name if color_enum_member else None
                            run_label = HIGHLIGHT_COLOR_TO_LABEL.get(color_name)

                        if run_label:
                            # This run is highlighted with a recognized color
                            if current_entity_label == run_label:
                                # Same label as current entity - extend it
                                current_entity_end = end_char
                            else:
                                # Different label - close current and start new
                                close_current_entity(entities, full_text)
                                current_entity_start = start_char
                                current_entity_end = end_char
                                current_entity_label = run_label
                        else:
                            # No highlight or unrecognized color - close current entity
                            close_current_entity(entities, full_text)

                        full_text += run_text
                        current_pos = end_char

                    # Close entity at end of paragraph (entities don't span paragraphs)
                    close_current_entity(entities, full_text)
                    full_text += "\n"
                    current_pos += 1

                # Close any remaining entity
                close_current_entity(entities, full_text)

                if entities:
                    tdoc.extracted_text = full_text.strip()
                    tdoc.save(update_fields=["extracted_text"])
                    train_data.append((tdoc.extracted_text, {"entities": entities}))
                    training_docs_used.append(tdoc)
            except Exception as e:
                print(f"Could not process training doc {tdoc.name}: {e}")

    if source in ("redactions", "both"):
        completed_docs = Document.objects.filter(status=Document.Status.COMPLETED)
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

    if train_set:
        db_train.to_disk(train_path)
    if dev_set:
        db_dev.to_disk(dev_path)


def train_model(source="redactions", user=None):
    """
    Train a new spaCy model using the config-driven pipeline.
    """
    # Check if another training task is already running
    # Tasks with success=None are still in progress
    running_tasks = Task.objects.filter(
        func="training.tasks.train_model",
        success__isnull=True,
    ).count()

    # If there's already a running task (not counting this one which hasn't started yet),
    # abort to prevent concurrent training
    if running_tasks > 0:
        print("Another training task is already in progress. Aborting.")
        return

    train_data, used_training_docs, used_case_docs = collect_training_data_detailed(source)

    if len(train_data) < 25:
        print(
            f"Not enough training data ({len(train_data)} \
                examples). Aborting."
        )
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
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        active_model = Model.objects.get(is_active=True)
        base_model_path = active_model.path
    except Model.DoesNotExist:
        active_model = None
        base_model_path = "en_core_web_lg"

    # Run spaCy train with subprocess
    config_path = Path(settings.BASE_DIR, "training", "config.cfg")
    cmd = [
        "python",
        "-m",
        "spacy",
        "train",
        str(config_path),
        "--output",
        str(output_dir),
        "--paths.train",
        str(train_file),
        "--paths.dev",
        str(dev_file),
        "--initialize.vectors",
        base_model_path,
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        # Clean up the output directory if training failed
        if output_dir.exists():
            shutil.rmtree(output_dir)
        raise

    # Load best model for evaluation scores
    nlp = spacy.load(output_dir / "model-best")
    scores = nlp.evaluate([Example.from_dict(nlp.make_doc(t), ann) for t, ann in train_data])

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

    # Find the corresponding training data for each document to get the text
    tdoc_texts = {tdoc: data[0] for tdoc, data in zip(used_training_docs, train_data, strict=False)}

    for tdoc, text in tdoc_texts.items():
        TrainingRunTrainingDoc.objects.create(training_run=training_run, document=tdoc)
        tdoc.extracted_text = text
        tdoc.processed = True
        tdoc.save(update_fields=["extracted_text", "processed"])

    for cdoc in used_case_docs:
        TrainingRunCaseDoc.objects.create(training_run=training_run, document=cdoc)

    print(
        f"Model trained and stored at {output_dir}, \
            DB updated, TrainingRun created."
    )
