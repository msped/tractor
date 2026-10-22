"""
SpanCat training, independent of Django.

Everything here is a function of its arguments: a corpus of annotated text, a
span-length ceiling, an output directory. Nothing reads the database, the
settings module or the clock, which is what lets the same code train a model
two ways — as the application's queued task, where the ORM supplies the
corpus and records the result, and as a standalone sweep that only needs a
folder of annotated DOCX files and somewhere to write to.

The parts that do belong to the application — collecting the corpus from
TrainingDocument and case Redaction rows, claiming the training slot,
honouring a stop request, registering the finished model — live in tasks.py
and reach in through the two callbacks below:

    should_stop(stage)  Called at each point a long run can be abandoned.
                        Raises to abandon it; the default never does.
    on_epoch(record)    Called with each epoch's EpochRecord as it completes,
                        for progress reporting.
"""

import logging
import random
import time
from collections import Counter
from dataclasses import dataclass, field

from spacy.training import Example
from spacy.util import compounding, minibatch

from .extraction import extract_annotated_text

logger = logging.getLogger(__name__)

# SpanCat is trained on top of this model's pretrained tok2vec weights, so it
# has to be present before a run can start. It is a pinned dependency of the
# project, so an environment installed from the lockfile already has it;
# ensure_base_model covers the one that was not.
BASE_MODEL = "en_core_web_lg"

HIGHLIGHT_COLOR_TO_LABEL = {
    "BRIGHT_GREEN": "THIRD_PARTY",
    "TURQUOISE": "OPERATIONAL",
}

CUSTOM_NER_LABELS = ["THIRD_PARTY", "OPERATIONAL"]

# The suggester ceiling the application uses unless told otherwise. Kept here
# rather than in settings so a run outside Django has the same default.
DEFAULT_MAX_SPAN_TOKENS = 40

MAX_EPOCHS = 15
PATIENCE = 3


class TrainingStopped(Exception):
    """Raised from anywhere in a run once a stop has been requested.

    An exception rather than a return value because a run has several long
    phases — reading documents, aligning annotations, then the epoch loop —
    and every one of them needs to be interruptible. Threading a flag back
    through each would mean every caller remembering to check it; raising
    puts the cleanup in one place.
    """


def _never_stop(stage):
    """The default should_stop: a run nobody can interrupt."""


@dataclass
class CorpusStats:
    """What the corpus looked like once aligned to tokens at a given ceiling.

    *token_lengths* counts annotations by their length in tokens, which is a
    property of the corpus and the tokenizer alone — not of the ceiling. One
    pass therefore answers what share of the corpus a ceiling leaves
    unreachable for every possible ceiling, not just the one used here.
    """

    total: int = 0
    dropped: int = 0
    split: int = 0
    pieces: int = 0
    token_lengths: Counter = field(default_factory=Counter)

    @property
    def kept(self):
        return self.total - self.dropped

    def over(self, ceiling):
        """How many annotations are longer than *ceiling* tokens."""
        return sum(
            n for length, n in self.token_lengths.items() if length > ceiling
        )

    def unreachable_share(self, ceiling):
        """The share of annotations a suggester at *ceiling* can never propose.

        This is the number that justifies one ceiling over another: an
        annotation longer than the ceiling is never offered as a candidate, so
        it cannot be scored, cannot be learned, and counts as a false negative
        at evaluation however good the model becomes.
        """
        if not self.total:
            return 0.0
        return self.over(ceiling) / self.total


@dataclass
class EpochRecord:
    """One epoch's result."""

    epoch: int
    loss: float
    precision: float
    recall: float
    f1: float
    seconds: float
    improved: bool

    def __str__(self):
        return (
            f"Epoch {self.epoch}/{MAX_EPOCHS} - "
            f"Loss: {self.loss:.4f} - "
            f"Dev F1: {self.f1:.4f} P: {self.precision:.4f} R: {self.recall:.4f}"
        )


def trim_spans(spans, text):
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


# Tokens ending in one of these close a clause or sentence, and so make a
# natural place to divide an over-long annotation. Semicolons matter as much
# as full stops here: this material is written as semicolon-delimited lists
# ("description provided; CCTV suggestions logged") at least as often as prose.
_BOUNDARY_SUFFIXES = (".", ";", "!", "?")


def split_long_span(span, label, max_tokens):
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


def load_annotated_docs(paths, labels=None):
    """Read annotated DOCX files into training data, without a database.

    Returns (train_data, skipped), where train_data holds the same
    (text, {"entities": [...]}) tuples the application's collector produces
    from TrainingDocument rows — the highlights are re-read from the file
    either way, so a folder of documents and the corresponding rows give a
    character-for-character identical corpus.
    """
    labels = labels or HIGHLIGHT_COLOR_TO_LABEL
    train_data = []
    skipped = []

    for path in paths:
        try:
            full_text, spans = extract_annotated_text(str(path), labels)
        except Exception as exc:
            logger.error("Could not read %s: %s", path, exc)
            skipped.append((str(path), str(exc)))
            continue

        if not full_text:
            skipped.append((str(path), "no text extracted"))
            continue

        entities = trim_spans(spans, full_text)
        if not entities:
            skipped.append((str(path), "no highlighted spans"))
            continue

        train_data.append((full_text, {"entities": entities}))

    return train_data, skipped


def base_model_present():
    """Whether the base model this trains on top of is installed."""
    import spacy.util

    return spacy.util.is_package(BASE_MODEL)


def ensure_base_model(download=True, log=None):
    """Make sure the base model is installed, fetching it if it is not.

    Called explicitly rather than from build_pipeline, because reaching the
    network is the caller's decision to make: the application's environment
    installs the model from the lockfile and should fail loudly if it is
    somehow missing, while a standalone run on a fresh machine would rather
    fetch it than stop.

    Returns True if the model was downloaded, False if it was already there.
    Raises RuntimeError when it is missing and *download* is False, or when
    the download leaves it still unusable.
    """
    log = log or logger.info

    if base_model_present():
        return False

    if not download:
        raise RuntimeError(
            f"{BASE_MODEL} is not installed. Install the project dependencies, "
            f"or run 'python -m spacy download {BASE_MODEL}'."
        )

    log(f"{BASE_MODEL} not found — downloading it (about 560MB)...")
    import spacy.cli

    spacy.cli.download(BASE_MODEL)

    if not base_model_present():
        raise RuntimeError(
            f"{BASE_MODEL} is still unavailable after downloading it. "
            f"Check the environment the download installed into."
        )

    log(f"{BASE_MODEL} installed.")
    return True


def build_pipeline(max_span_tokens=DEFAULT_MAX_SPAN_TOKENS):
    """Build a SpanCat spaCy pipeline seeded with en_core_web_lg's pretrained tok2vec weights."""
    import spacy

    nlp = spacy.load(BASE_MODEL)

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
    # At the default of 40 that leaves ~1.2% of this corpus's annotations
    # unreachable, almost all of them long free-text log entries. Raising it
    # costs roughly linear extra time but grows peak memory considerably
    # faster, and worsens the negative-to-positive candidate ratio — this
    # model has failed on class imbalance before, so compare P/R/F1 against
    # the previous run rather than assuming more coverage is better.
    # CorpusStats.unreachable_share quantifies the coverage side of that
    # trade-off without training anything.
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


def prepare_examples(nlp, train_data, max_tokens=None, should_stop=None):
    """Convert (text, annotations) tuples into spaCy Example objects.

    Annotations longer than *max_tokens* are divided at clause boundaries
    rather than left whole, since the suggester would never propose them.
    Pass None to leave them intact.

    Returns (examples, CorpusStats).

    Calls *should_stop* every tenth document. This phase builds a Doc per
    document and is slow and memory-hungry on a large corpus, so it has to be
    interruptible — a stop that only took effect once epoch 1 began would
    appear to do nothing for the longest part of a run.
    """
    should_stop = should_stop or _never_stop
    examples = []
    stats = CorpusStats()

    for index, (text, annotations) in enumerate(train_data):
        if index and index % 10 == 0:
            should_stop(f"while preparing example {index}")

        doc = nlp.make_doc(text)
        ref = doc.copy()
        spans = []
        for start, end, label in annotations["entities"]:
            stats.total += 1
            span = ref.char_span(
                start, end, label=label, alignment_mode="contract"
            )
            if not span:
                stats.dropped += 1
                continue

            stats.token_lengths[len(span)] += 1

            if max_tokens and len(span) > max_tokens:
                pieces = split_long_span(span, label, max_tokens)
                if pieces:
                    stats.split += 1
                    stats.pieces += len(pieces)
                    spans.extend(pieces)
                    continue

            spans.append(span)
        ref.spans["sc"] = spans
        examples.append(Example(doc, ref))

    return examples, stats


def run_training_loop(
    nlp,
    train_examples,
    dev_examples,
    output_dir,
    should_stop=None,
    on_epoch=None,
):
    """Train for a fixed number of epochs with early stopping on dev F1.

    Returns (best_scores, history). The best model so far is written to
    *output_dir* each time dev F1 improves, so what is on disk at the end is
    the best epoch's model rather than the last one's.

    Propagates whatever *should_stop* raises; the caller discards the output
    directory, since a half-trained model is not worth keeping and
    registering one nobody chose to make would be worse.
    """
    should_stop = should_stop or _never_stop
    best_f1 = 0.0
    epochs_without_improvement = 0
    best_scores = {}
    history = []

    optimizer = nlp.resume_training()
    optimizer.learn_rate = 0.001

    for epoch in range(MAX_EPOCHS):
        should_stop(f"at the start of epoch {epoch + 1}")

        started = time.monotonic()
        random.shuffle(train_examples)
        losses = {}

        batches = minibatch(train_examples, size=compounding(4.0, 32.0, 1.001))
        for batch in batches:
            # Checked before every batch, not every nth. A batch can take a
            # long time at a high suggester ceiling, so an interval measured
            # in batches is an unpredictable interval in seconds; one tiny
            # query per batch is nothing beside the batch itself.
            should_stop(f"during epoch {epoch + 1}")
            nlp.update(batch, sgd=optimizer, drop=0.2, losses=losses)

        # Evaluate on dev set
        scores = nlp.evaluate(dev_examples)
        dev_f1 = scores.get("spans_sc_f", 0.0)

        improved = dev_f1 > best_f1
        if improved:
            best_f1 = dev_f1
            best_scores = scores
            epochs_without_improvement = 0
            nlp.to_disk(output_dir)
        else:
            epochs_without_improvement += 1

        record = EpochRecord(
            epoch=epoch + 1,
            loss=losses.get("spancat", 0.0),
            precision=scores.get("spans_sc_p", 0.0),
            recall=scores.get("spans_sc_r", 0.0),
            f1=dev_f1,
            seconds=time.monotonic() - started,
            improved=improved,
        )
        history.append(record)
        if on_epoch:
            on_epoch(record)

        if epochs_without_improvement >= PATIENCE:
            if on_epoch:
                on_epoch(
                    f"Early stopping at epoch {epoch + 1} "
                    f"(no improvement for {PATIENCE} epochs)"
                )
            break

    # If no improvement was ever saved (all F1=0), save final state
    if best_f1 == 0.0:
        nlp.to_disk(output_dir)
        best_scores = scores

    return best_scores, history
