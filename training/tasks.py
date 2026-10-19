import logging
import random
import shutil
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django_q.models import Task
from spacy.training import Example
from spacy.util import compounding, minibatch

from cases.models import Document

from .extraction import extract_annotated_text
from .models import (
    Model,
    TrainingDocument,
    TrainingRun,
    TrainingRunCaseDoc,
    TrainingRunTrainingDoc,
)

logger = logging.getLogger(__name__)

HIGHLIGHT_COLOR_TO_LABEL = {
    "BRIGHT_GREEN": "THIRD_PARTY",
    "TURQUOISE": "OPERATIONAL",
}

# Case redactions: only OP_DATA feeds SpanCat training. PII redactions are excluded
# because they originate from GLiNER suggestions which may be incorrect, and training
# on them would cause SpanCat to learn and reinforce those mistakes.
REDACTION_TYPE_TO_ENTITY_LABEL = {
    "OP_DATA": "OPERATIONAL",
}

CUSTOM_NER_LABELS = ["THIRD_PARTY", "OPERATIONAL"]


def _trim_spans(spans, text):
    """
    Drop whitespace from the edges of each highlighted span, and discard any
    span that is nothing but whitespace.

    An annotator's highlight routinely runs a space past the word it covers.
    Left alone those edges straddle token boundaries, and spaCy cannot align a
    span to tokens it only partly covers — the example is silently dropped.
    """
    trimmed = []
    for start, end, label in spans:
        fragment = text[start:end]
        stripped = fragment.strip()
        if not stripped:
            continue
        lead = len(fragment) - len(fragment.lstrip())
        trail = len(fragment) - len(fragment.rstrip())
        trimmed.append((start + lead, end - trail, label))
    return trimmed


def collect_training_data_detailed(source="both"):
    """Collect labelled training examples from training documents and/or accepted case redactions."""
    train_data = []
    training_docs_used = []
    case_docs_used = []

    if source in ("training_docs", "both"):
        # Get ALL training documents for cumulative training
        training_docs = TrainingDocument.objects.all()
        for tdoc in training_docs:
            try:
                full_text, spans = extract_annotated_text(
                    tdoc.original_file.path, HIGHLIGHT_COLOR_TO_LABEL
                )
                if not full_text:
                    continue

                entities = _trim_spans(spans, full_text)

                if entities:
                    tdoc.extracted_text = full_text
                    tdoc.save(update_fields=["extracted_text"])
                    train_data.append((full_text, {"entities": entities}))
                    training_docs_used.append(tdoc)
            except Exception as e:
                logger.error(
                    "Could not process training doc %s: %s", tdoc.name, e
                )

    if source in ("redactions", "both"):
        completed_docs = Document.objects.filter(
            status=Document.Status.COMPLETED
        ).order_by("-uploaded_at")[:500]
        for doc in completed_docs:
            text = doc.extracted_text
            if not text:
                continue

            entities = []
            for redaction in doc.redactions.trainable():
                label = REDACTION_TYPE_TO_ENTITY_LABEL.get(
                    redaction.redaction_type
                )
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
    """Build a SpanCat spaCy pipeline seeded with en_core_web_lg's pretrained tok2vec weights."""
    import spacy

    nlp = spacy.load("en_core_web_lg")

    # Remove all pipes except tok2vec
    for pipe_name in list(nlp.pipe_names):
        if pipe_name != "tok2vec":
            nlp.remove_pipe(pipe_name)

    # Get tok2vec output width dynamically
    tok2vec_width = nlp.get_pipe("tok2vec").model.get_dim("nO")

    # Configure spancat with ngram suggester and tok2vec listener.
    #
    # The suggester's maximum size is a hard ceiling on what the model can
    # ever predict: a gold span longer than this is never proposed as a
    # candidate, so it cannot be scored, cannot be learned, and counts as a
    # false negative at evaluation. At the previous ceiling of 20 tokens,
    # 6.2% of the 18,561 annotation spans in the training corpus were
    # unreachable — almost all OPERATIONAL, the long free-text log entries
    # and summaries these reports are full of — which capped achievable
    # recall at 0.938 however good the model became.
    #
    # Span length beyond SPANCAT_MAX_SPAN_TOKENS is unreachable: the suggester
    # never proposes a longer candidate, so the model cannot score it, cannot
    # learn it, and it counts as a false negative at evaluation.
    #
    # At the default of 40 that leaves ~1.2% of this corpus's annotations
    # unreachable, almost all of them long free-text log entries. Raising it
    # costs roughly linear extra time but grows peak memory considerably
    # faster, and worsens the negative-to-positive candidate ratio — this
    # model has failed on class imbalance before, so compare P/R/F1 against
    # the previous run rather than assuming more coverage is better.
    max_span_tokens = getattr(settings, "SPANCAT_MAX_SPAN_TOKENS", 40)
    spancat_config = {
        "suggester": {
            "@misc": "spacy.ngram_suggester.v1",
            "sizes": list(range(1, max_span_tokens + 1)),
        },
        "model": {
            "@architectures": "spacy.SpanCategorizer.v1",
            "scorer": {
                "@layers": "spacy.LinearLogistic.v1",
                "nO": None,
                "nI": None,
            },
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


class TrainingStopped(Exception):
    """Raised from anywhere in a run once a stop has been requested.

    An exception rather than a return value because a run has several long
    phases — reading documents, aligning annotations, then the epoch loop —
    and every one of them needs to be interruptible. Threading a flag back
    through each would mean every caller remembering to check it; raising
    puts the cleanup in one place.
    """


def _stop_requested():
    """Whether someone has asked this run to stop (see TrainingControl)."""
    from .models import TrainingControl

    return TrainingControl.objects.filter(pk=1, cancel_requested=True).exists()


def _abort_if_stopped(stage):
    """Give up the run if a stop has been asked for by the time *stage* begins."""
    if _stop_requested():
        raise TrainingStopped(stage)


# Tokens ending in one of these close a clause or sentence, and so make a
# natural place to divide an over-long annotation. Semicolons matter as much
# as full stops here: this material is written as semicolon-delimited lists
# ("description provided; CCTV suggestions logged") at least as often as prose.
_BOUNDARY_SUFFIXES = (".", ";", "!", "?")


def _split_long_span(span, label, max_tokens):
    """
    Divide *span* into consecutive pieces of at most *max_tokens* tokens.

    An annotation longer than the suggester's ceiling can never be proposed as
    a candidate, so it teaches the model nothing and counts against recall at
    evaluation. Splitting it makes the material learnable: the pieces are
    predicted separately and the existing adjacent-span merging rejoins them
    for the reviewer.

    Pieces end at a clause or sentence boundary wherever one falls inside the
    window, and are cut at the ceiling where none does. An imperfect boundary
    is cheap here — the pieces still cover exactly the same text between them,
    and the only cost is that the model learns a slightly odd division.
    """
    pieces = []
    start = 0
    while start < len(span):
        window_end = min(start + max_tokens, len(span))

        split_at = window_end
        if window_end < len(span):
            # Prefer the last boundary inside the window; never split so early
            # that a piece is mostly empty.
            for i in range(window_end - 1, start, -1):
                if span[i].text.endswith(_BOUNDARY_SUFFIXES):
                    split_at = i + 1
                    break

        piece = span[start:split_at]
        if len(piece) == 0:  # pragma: no cover - guards against a stuck loop
            break
        pieces.append(
            piece.doc.char_span(
                piece.start_char,
                piece.end_char,
                label=label,
                alignment_mode="contract",
            )
        )
        start = split_at

    return [p for p in pieces if p is not None]


def _prepare_examples(nlp, train_data, max_tokens=None):
    """Convert (text, annotations) tuples into spaCy Example objects for training.

    Annotations longer than *max_tokens* are divided at clause boundaries
    rather than left whole, since the suggester would never propose them.
    Pass None to leave them intact.

    Raises TrainingStopped if a stop is requested partway. This phase builds a
    Doc per document and is slow and memory-hungry on a large corpus, so it
    has to be interruptible — a stop that only took effect once epoch 1 began
    would appear to do nothing for the longest part of a run.
    """
    examples = []
    total_entities = 0
    dropped_entities = 0
    split_entities = 0
    pieces_made = 0

    for index, (text, annotations) in enumerate(train_data):
        if index and index % 10 == 0:
            _abort_if_stopped(f"while preparing example {index}")

        doc = nlp.make_doc(text)
        ref = doc.copy()
        spans = []
        for start, end, label in annotations["entities"]:
            total_entities += 1
            span = ref.char_span(
                start, end, label=label, alignment_mode="contract"
            )
            if not span:
                dropped_entities += 1
                continue

            if max_tokens and len(span) > max_tokens:
                pieces = _split_long_span(span, label, max_tokens)
                if pieces:
                    split_entities += 1
                    pieces_made += len(pieces)
                    spans.extend(pieces)
                    continue

            spans.append(span)
        ref.spans["sc"] = spans
        examples.append(Example(doc, ref))

    if total_entities > 0:
        print(
            f"Entity alignment: {total_entities - dropped_entities}/{total_entities} kept, {dropped_entities} dropped"
        )
    if split_entities:
        print(
            f"Long annotations divided at clause boundaries: "
            f"{split_entities} spans over {max_tokens} tokens became "
            f"{pieces_made} learnable pieces"
        )

    return examples


def _run_training_loop(nlp, train_examples, dev_examples, output_dir):
    """Train the SpanCat model for a fixed number of iterations with early stopping.

    Raises TrainingStopped if a stop is requested; the caller discards the
    output directory, since a half-trained model is not worth keeping and
    registering one nobody chose to make would be worse.
    """
    max_epochs = 15
    patience = 3
    best_f1 = 0.0
    epochs_without_improvement = 0
    best_scores = {}

    optimizer = nlp.resume_training()
    optimizer.learn_rate = 0.001

    for epoch in range(max_epochs):
        _abort_if_stopped(f"at the start of epoch {epoch + 1}")

        random.shuffle(train_examples)
        losses = {}

        batches = minibatch(train_examples, size=compounding(4.0, 32.0, 1.001))
        for batch in batches:
            # Checked before every batch, not every nth. A batch can take a
            # long time at a high suggester ceiling, so an interval measured
            # in batches is an unpredictable interval in seconds; one tiny
            # query per batch is nothing beside the batch itself.
            _abort_if_stopped(f"during epoch {epoch + 1}")
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
            print(
                f"Early stopping at epoch {epoch + 1} (no improvement for {patience} epochs)"
            )
            break

    # If no improvement was ever saved (all F1=0), save final state
    if best_f1 == 0.0:
        nlp.to_disk(output_dir)
        best_scores = scores

    return best_scores


def train_model(source="redactions", user=None):
    """Train a new SpanCat model from collected redaction data and save it to nlp_models/."""
    # Check if another training task is already running
    running_tasks = Task.objects.filter(
        func="training.tasks.train_model",
        success__isnull=True,
    ).count()

    if running_tasks > 0:
        print("Another training task is already in progress. Aborting.")
        return

    # Clear any stop left over from a previous run, so a stale flag cannot
    # kill this one before it starts. Done before reading documents, since
    # that is itself slow enough to be worth interrupting.
    from .models import TrainingControl

    control = TrainingControl.get()
    if control.cancel_requested:
        control.cancel_requested = False
        control.save(update_fields=["cancel_requested"])

    train_data, used_training_docs, used_case_docs = (
        collect_training_data_detailed(source)
    )

    if len(train_data) < 75:
        print(
            f"Not enough training data ({len(train_data)} examples). Aborting."
        )
        return

    if _stop_requested():
        # Nothing has been created yet, so there is nothing to clean up.
        control.cancel_requested = False
        control.save(update_fields=["cancel_requested"])
        print("Training stopped on request before it began.")
        return

    # Prepare output dir
    model_name = f"model_{source}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = Path(settings.BASE_DIR, "nlp_models", model_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Annotations are divided to fit the same ceiling the suggester uses, so
    # nothing in the training data is unreachable by construction.
    max_tokens = getattr(settings, "SPANCAT_MAX_SPAN_TOKENS", 40)

    try:
        # Build SpanCat pipeline (always from en_core_web_lg for transfer learning)
        nlp = _build_spancat_pipeline()

        # Initialize the pipeline with example data
        def get_examples():
            return _prepare_examples(nlp, train_data[:10], max_tokens)

        _abort_if_stopped("before initialising the pipeline")
        nlp.initialize(get_examples)

        # Prepare all examples
        _abort_if_stopped("before preparing examples")
        all_examples = _prepare_examples(nlp, train_data, max_tokens)

        # Split 80/20 train/dev
        random.shuffle(all_examples)
        split_point = int(len(all_examples) * 0.8)
        train_examples = all_examples[:split_point]
        dev_examples = all_examples[split_point:]

        # Train and save best model
        best_scores = _run_training_loop(
            nlp, train_examples, dev_examples, output_dir
        )

    except TrainingStopped as stop:
        # Discard the partial model rather than registering something nobody
        # asked for. The previously active model is untouched throughout.
        if output_dir.exists():
            shutil.rmtree(output_dir)
        control.cancel_requested = False
        control.save(update_fields=["cancel_requested"])
        print(
            f"Training stopped on request ({stop}). No model was registered."
        )
        return

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
    tdoc_texts = {
        tdoc: data[0]
        for tdoc, data in zip(used_training_docs, train_data, strict=False)
    }

    for tdoc, text in tdoc_texts.items():
        TrainingRunTrainingDoc.objects.create(
            training_run=training_run, document=tdoc
        )
        tdoc.extracted_text = text
        tdoc.processed = True
        tdoc.save(update_fields=["extracted_text", "processed"])

    for cdoc in used_case_docs:
        TrainingRunCaseDoc.objects.create(
            training_run=training_run, document=cdoc
        )

    print(
        f"Model trained and stored at {output_dir}, DB updated, TrainingRun created."
    )
