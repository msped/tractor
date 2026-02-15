import random
import shutil
from pathlib import Path

import spacy
from django.conf import settings
from django.utils import timezone
from django_q.models import Task
from docx import Document as DocxDocument
from spacy.training import Example
from spacy.util import compounding, minibatch

from cases.models import Document, Redaction

from .models import (
    Model,
    TrainingDocument,
    TrainingRun,
    TrainingRunCaseDoc,
    TrainingRunTrainingDoc,
)

HIGHLIGHT_COLOR_TO_LABEL = {
    "BRIGHT_GREEN": "THIRD_PARTY",
    "TURQUOISE": "OPERATIONAL",
}

REDACTION_TYPE_TO_ENTITY_LABEL = {
    "PII": "THIRD_PARTY",
    "OP_DATA": "OPERATIONAL",
}

CUSTOM_NER_LABELS = ["THIRD_PARTY", "OPERATIONAL"]


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
                label = REDACTION_TYPE_TO_ENTITY_LABEL.get(redaction.redaction_type)
                if label:
                    entities.append(
                        (
                            redaction.start_char,
                            redaction.end_char,
                            label,
                        )
                    )
            if entities:
                train_data.append((text, {"entities": entities}))
                case_docs_used.append(doc)

    return train_data, training_docs_used, case_docs_used


def _build_spancat_pipeline():
    """
    Build a SpanCat pipeline using en_core_web_lg's pretrained tok2vec.

    Loads the base model, strips all pipes except tok2vec, then adds a
    spancat component configured with an ngram suggester and a
    Tok2VecListener that reuses the frozen pretrained embeddings.
    """
    nlp = spacy.load("en_core_web_lg")

    # Remove all pipes except tok2vec
    for pipe_name in list(nlp.pipe_names):
        if pipe_name != "tok2vec":
            nlp.remove_pipe(pipe_name)

    # Get tok2vec output width dynamically
    tok2vec_width = nlp.get_pipe("tok2vec").model.get_dim("nO")

    # Configure spancat with ngram suggester and tok2vec listener
    spancat_config = {
        "suggester": {
            "@misc": "spacy.ngram_suggester.v1",
            "sizes": list(range(1, 51)),
        },
        "model": {
            "@architectures": "spacy.SpanCategorizer.v1",
            "scorer": {"@layers": "spacy.LinearLogistic.v1", "nO": None, "nI": None},
            "reducer": {
                "@layers": "spacy.mean_max_reducer.v1",
                "hidden_size": 128,
            },
            "tok2vec": {
                "@architectures": "spacy.Tok2VecListener.v1",
                "width": tok2vec_width,
                "upstream": "tok2vec",
            },
        },
    }

    spancat = nlp.add_pipe("spancat", config=spancat_config)
    for label in CUSTOM_NER_LABELS:
        spancat.add_label(label)

    return nlp


def _prepare_examples(nlp, train_data):
    """
    Convert (text, {"entities": [...]}) tuples to spaCy Example objects
    with entities set as doc.spans["sc"] for SpanCat training.
    """
    examples = []
    total_entities = 0
    dropped_entities = 0

    for text, annotations in train_data:
        doc = nlp.make_doc(text)
        ref = doc.copy()
        spans = []
        for start, end, label in annotations["entities"]:
            total_entities += 1
            span = ref.char_span(start, end, label=label, alignment_mode="contract")
            if span:
                spans.append(span)
            else:
                dropped_entities += 1
        ref.spans["sc"] = spans
        examples.append(Example(doc, ref))

    if total_entities > 0:
        print(
            f"Entity alignment: {total_entities - dropped_entities}/{total_entities} kept, {dropped_entities} dropped"
        )

    return examples


def _run_training_loop(nlp, train_examples, dev_examples, output_dir):
    """
    Train the SpanCat model with early stopping.

    Returns the best scores dict from evaluation.
    """
    max_epochs = 30
    patience = 10
    best_f1 = 0.0
    epochs_without_improvement = 0
    best_scores = {}

    optimizer = nlp.resume_training()
    optimizer.learn_rate = 0.001

    for epoch in range(max_epochs):
        random.shuffle(train_examples)
        losses = {}

        batches = minibatch(train_examples, size=compounding(4.0, 32.0, 1.001))
        for batch in batches:
            nlp.update(batch, sgd=optimizer, drop=0.2, losses=losses)

        # Evaluate on dev set
        scores = nlp.evaluate(dev_examples)
        dev_f1 = scores.get("spans_sc_f", 0.0)
        dev_p = scores.get("spans_sc_p", 0.0)
        dev_r = scores.get("spans_sc_r", 0.0)

        print(
            f"Epoch {epoch + 1}/{max_epochs} - "
            f"Loss: {losses.get('spancat', 0.0):.4f} - "
            f"Dev F1: {dev_f1:.4f} P: {dev_p:.4f} R: {dev_r:.4f}"
        )

        if dev_f1 > best_f1:
            best_f1 = dev_f1
            best_scores = scores
            epochs_without_improvement = 0
            nlp.to_disk(output_dir)
        else:
            epochs_without_improvement += 1

        if epochs_without_improvement >= patience:
            print(f"Early stopping at epoch {epoch + 1} (no improvement for {patience} epochs)")
            break

    # If no improvement was ever saved (all F1=0), save final state
    if best_f1 == 0.0:
        nlp.to_disk(output_dir)
        best_scores = scores

    return best_scores


def train_model(source="redactions", user=None):
    """
    Train a SpanCat model using en_core_web_lg's pretrained tok2vec
    with transfer learning.
    """
    # Check if another training task is already running
    running_tasks = Task.objects.filter(
        func="training.tasks.train_model",
        success__isnull=True,
    ).count()

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

    # Prepare output dir
    model_name = f"model_{source}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = Path(settings.BASE_DIR, "nlp_models", model_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Build SpanCat pipeline (always from en_core_web_lg for transfer learning)
        nlp = _build_spancat_pipeline()

        # Initialize the pipeline with example data
        def get_examples():
            return _prepare_examples(nlp, train_data[:10])

        nlp.initialize(get_examples)

        # Prepare all examples
        all_examples = _prepare_examples(nlp, train_data)

        # Split 80/20 train/dev
        random.shuffle(all_examples)
        split_point = int(len(all_examples) * 0.8)
        train_examples = all_examples[:split_point]
        dev_examples = all_examples[split_point:]

        # Train and save best model
        best_scores = _run_training_loop(nlp, train_examples, dev_examples, output_dir)

    except Exception:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        raise

    # Register in DB
    new_model = Model.objects.create(
        name=model_name,
        path=str(output_dir),
        is_active=False,
        precision=best_scores.get("spans_sc_p"),
        recall=best_scores.get("spans_sc_r"),
        f1_score=best_scores.get("spans_sc_f"),
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
