import logging
import os
import random
import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from cases.models import Document

from .extraction import extract_annotated_text
from .models import (
    Model,
    TrainingDocument,
    TrainingRun,
    TrainingRunCaseDoc,
    TrainingRunTrainingDoc,
)
from .spancat import (
    CUSTOM_NER_LABELS,
    DEFAULT_MAX_SPAN_TOKENS,
    HIGHLIGHT_COLOR_TO_LABEL,
    TrainingStopped,
    build_pipeline,
    prepare_examples,
    run_training_loop,
    trim_spans,
)

logger = logging.getLogger(__name__)

# Re-exported so the names this module has always offered keep working, and so
# that what belongs to training itself stays in one place.
__all__ = [
    "CUSTOM_NER_LABELS",
    "HIGHLIGHT_COLOR_TO_LABEL",
    "TrainingStopped",
    "collect_training_data_detailed",
    "train_model",
]

# Case redactions: only OP_DATA feeds SpanCat training. PII redactions are excluded
# because they originate from GLiNER suggestions which may be incorrect, and training
# on them would cause SpanCat to learn and reinforce those mistakes.
REDACTION_TYPE_TO_ENTITY_LABEL = {
    "OP_DATA": "OPERATIONAL",
}

# Kept under its old name: the extraction parity tests and this module's own
# collector both reach for it, and it reads as part of collecting a corpus.
_trim_spans = trim_spans


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
    """Build the SpanCat pipeline at the ceiling this deployment is configured for."""
    return build_pipeline(
        getattr(settings, "SPANCAT_MAX_SPAN_TOKENS", DEFAULT_MAX_SPAN_TOKENS)
    )


def _stop_requested():
    """Whether someone has asked this run to stop (see TrainingControl)."""
    from .models import TrainingControl

    return TrainingControl.objects.filter(pk=1, cancel_requested=True).exists()


# How often a run reports that it is still alive. Frequent enough that an
# abandoned run is noticed quickly, rare enough that the write is irrelevant
# beside the training itself.
_HEARTBEAT_EVERY = timedelta(seconds=30)
_last_heartbeat = None


def _beat():
    """Record that this run is still going, at most once per interval."""
    global _last_heartbeat
    from .models import TrainingControl

    now = timezone.now()
    if _last_heartbeat and now - _last_heartbeat < _HEARTBEAT_EVERY:
        return
    _last_heartbeat = now
    TrainingControl.objects.filter(pk=1).update(heartbeat_at=now)


def _claim_run():
    """
    Mark a run as started, refusing if one is already going.

    Returns the TrainingControl row, or None when another run holds it. Two
    concurrent trainings would simply double the machine's load for no
    benefit, and this used to be possible because the old guard looked at
    django-q Task rows, which only exist once a task has finished.
    """
    global _last_heartbeat
    from .models import TrainingControl

    control = TrainingControl.get()
    if control.is_running:
        print(
            f"A training run is already in progress (pid {control.pid}, "
            f"started {control.started_at}). Aborting."
        )
        return None

    if control.is_stale:
        print(
            f"Replacing an abandoned run (pid {control.pid}, last seen "
            f"{control.heartbeat_at})."
        )

    now = timezone.now()
    _last_heartbeat = now
    control.cancel_requested = False
    control.started_at = now
    control.heartbeat_at = now
    control.pid = os.getpid()
    control.save(
        update_fields=[
            "cancel_requested",
            "started_at",
            "heartbeat_at",
            "pid",
        ]
    )
    return control


def _release_run():
    """Clear the running marker. Safe to call however the run ended."""
    global _last_heartbeat
    from .models import TrainingControl

    _last_heartbeat = None
    TrainingControl.objects.filter(pk=1).update(
        cancel_requested=False,
        started_at=None,
        heartbeat_at=None,
        pid=None,
    )


def _abort_if_stopped(stage):
    """Give up the run if a stop has been asked for by the time *stage* begins.

    Doubles as the heartbeat: these are the points a run passes through
    regularly, so reporting life here costs nothing extra and means a run
    that stops checking in really has stopped working.
    """
    _beat()
    if _stop_requested():
        raise TrainingStopped(stage)


# Tokens ending in one of these close a clause or sentence, and so make a
# natural place to divide an over-long annotation. Semicolons matter as much
# as full stops here: this material is written as semicolon-delimited lists
# ("description provided; CCTV suggestions logged") at least as often as prose.
def _prepare_examples(nlp, train_data, max_tokens=None):
    """Convert collected training data into Examples, reporting what it found.

    The counts are worth printing rather than discarding: a sudden rise in
    dropped annotations means the extraction and the stored offsets have
    drifted apart, and the number divided at the ceiling says how much of the
    corpus the ceiling was too low for.
    """
    examples, stats = prepare_examples(
        nlp, train_data, max_tokens, should_stop=_abort_if_stopped
    )

    if stats.total > 0:
        print(
            f"Entity alignment: {stats.kept}/{stats.total} kept, "
            f"{stats.dropped} dropped"
        )
    if stats.split:
        print(
            f"Long annotations divided at clause boundaries: "
            f"{stats.split} spans over {max_tokens} tokens became "
            f"{stats.pieces} learnable pieces"
        )

    return examples


def _run_training_loop(nlp, train_examples, dev_examples, output_dir):
    """Train the SpanCat model, reporting each epoch and honouring a stop request.

    Raises TrainingStopped if a stop is requested; the caller discards the
    output directory, since a half-trained model is not worth keeping and
    registering one nobody chose to make would be worse.
    """
    best_scores, _history = run_training_loop(
        nlp,
        train_examples,
        dev_examples,
        output_dir,
        should_stop=_abort_if_stopped,
        on_epoch=print,
    )
    return best_scores


def train_model(source="redactions", user=None):
    """Train a new SpanCat model from collected redaction data and save it to nlp_models/.

    Claims the single training slot for the duration, so a second run cannot
    start alongside this one and double the machine's load, and so the run
    stays visible and stoppable from the UI for as long as it lasts.
    """
    if _claim_run() is None:
        return

    try:
        _train_model_inner(source)
    finally:
        # Whatever happened — finished, stopped, or raised — the slot is
        # given back. Only an outright kill can leave it held, and that is
        # precisely the case the stale heartbeat is there to reveal.
        _release_run()


def _train_model_inner(source):
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
