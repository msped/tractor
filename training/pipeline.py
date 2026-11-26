import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from cases.span_merging import REMOVAL_GAP_CHARS

logger = logging.getLogger(__name__)

# The label a gap-fill stage cuts down to uncovered text; its other labels
# keep drop-on-overlap (ADR-0005).
GAP_FILL_LABEL = "OPERATIONAL"


def _close_thread_connections(stage):
    """Wrap a stage so the worker thread's DB connections are closed after it runs.

    Stages execute on short-lived ThreadPoolExecutor threads; any ORM query in a
    stage (e.g. loading custom recognizers) opens a per-thread connection that
    Django never closes for bare threads. With persistent connections
    (CONN_MAX_AGE) those sessions leak on every pipeline run — and block
    dropping the test database in CI.
    """

    def wrapper(text):
        from django.db import connections

        try:
            return stage(text)
        finally:
            connections.close_all()

    return wrapper


def ranges_overlap(start, end, other_start, other_end):
    """Whether [start, end) and [other_start, other_end) share a character."""
    return start < other_end and end > other_start


def _deduplicate_entities(
    primary_entities, secondary_entities, allow_superset=False
):
    """Keep primary entities; add secondary only where no overlap with primary exists.

    When allow_superset=True: if a secondary entity strictly contains one or more
    primary entities (all with the same label) and doesn't partially overlap any other
    primary entity, the secondary span replaces those primaries. This lets SpanCat
    extend the boundaries of a Custom Presidio match when it has learned more context
    (e.g. "OIC / HUGHES, R. #0723222" vs Presidio's "HUGHES, R. #0723222").
    Superset replacement is intentionally off for all other stage pairs so that lower-
    priority extractors (GLiNER, Gemma) cannot widen higher-priority precise matches.
    """
    combined = list(primary_entities)
    for sec_ent in secondary_entities:
        s, e, lbl = (
            sec_ent["start_char"],
            sec_ent["end_char"],
            sec_ent.get("label"),
        )

        if allow_superset:
            superset_indices = [
                i
                for i, ent in enumerate(combined)
                if (
                    s <= ent["start_char"]
                    and e >= ent["end_char"]
                    and (s < ent["start_char"] or e > ent["end_char"])
                    and lbl == ent.get("label")
                )
            ]
            other_overlap_indices = [
                i
                for i, ent in enumerate(combined)
                if i not in superset_indices
                and ranges_overlap(s, e, ent["start_char"], ent["end_char"])
            ]

            if superset_indices and not other_overlap_indices:
                for idx in sorted(superset_indices, reverse=True):
                    combined.pop(idx)
                combined.append(sec_ent)
                continue
        else:
            other_overlap_indices = [
                i
                for i, ent in enumerate(combined)
                if ranges_overlap(s, e, ent["start_char"], ent["end_char"])
            ]

        if not other_overlap_indices:
            combined.append(sec_ent)
    return combined


def _uncovered_runs(start, end, covering):
    """The runs of [start, end) that no span in *covering* touches, in order."""
    holes = sorted(
        (max(start, span["start_char"]), min(end, span["end_char"]))
        for span in covering
        if ranges_overlap(start, end, span["start_char"], span["end_char"])
    )
    runs = []
    pos = start
    for hole_start, hole_end in holes:
        if hole_start > pos:
            runs.append((pos, hole_start))
        pos = max(pos, hole_end)
    if pos < end:
        runs.append((pos, end))
    return runs


def _trim_separators(text, start, end):
    """Narrow [start, end) past whitespace and separator punctuation."""
    while start < end and text[start] in REMOVAL_GAP_CHARS:
        start += 1
    while end > start and text[end - 1] in REMOVAL_GAP_CHARS:
        end -= 1
    return start, end


def _fill_gaps(primary_entities, secondary_entities, text, min_chars):
    """Add a gap-fill stage's spans to *primary_entities* (ADR-0005).

    An OPERATIONAL span nothing touches is added as it is.  One that overlaps
    anything is cut into the runs no span covers, of any label; each run is
    trimmed of separators (the characters the removal export treats as
    nothing between redactions), and kept as its own span if it has a letter
    or digit and at least *min_chars* characters.  Every other label is
    dropped on any overlap, as in _deduplicate_entities.  Spans are taken in
    order and what is kept covers later spans, so pieces never overlap.
    """
    combined = list(primary_entities)
    for span in secondary_entities:
        start, end = span["start_char"], span["end_char"]
        if span.get("label") != GAP_FILL_LABEL:
            if not _overlaps_any(span, combined):
                combined.append(span)
            continue

        runs = _uncovered_runs(start, end, combined)
        if runs == [(start, end)]:
            combined.append(span)
            continue
        for run_start, run_end in runs:
            piece_start, piece_end = _trim_separators(text, run_start, run_end)
            piece = text[piece_start:piece_end]
            if len(piece) < min_chars or not any(c.isalnum() for c in piece):
                continue
            combined.append(
                {
                    **span,
                    "text": piece,
                    "start_char": piece_start,
                    "end_char": piece_end,
                }
            )
    return combined


def _non_fatal(stage):
    """Wrap a stage so exceptions log a warning and return [] instead of propagating."""

    def wrapper(text):
        try:
            return stage(text)
        except Exception as exc:
            logger.warning("Non-fatal extractor raised unexpectedly: %s", exc)
            return []

    return wrapper


@dataclass(frozen=True)
class SpanRuleResult:
    """
    What a span rule hands back to the pipeline.

    ``stage_results`` is the per-detector span lists, one per stage and in
    stage order, with whatever the rule dropped removed.  ``added`` is the
    rule's own spans, which outrank every detector.
    """

    stage_results: list
    added: list = field(default_factory=list)


def _overlaps_any(span, others):
    """Whether *span* shares a character with any span in *others*."""
    return any(
        ranges_overlap(
            span["start_char"],
            span["end_char"],
            other["start_char"],
            other["end_char"],
        )
        for other in others
    )


@dataclass
class ExtractionPipeline:
    """
    Runs extractors concurrently and deduplicates in priority order.

    stages[0] has highest priority; later stages are dropped on overlap.
    superset_stage_indices marks which stages may extend earlier predictions via
    the superset replacement rule (see _deduplicate_entities).
    gap_fill_stage_indices marks which stages' OPERATIONAL spans instead fill
    the text nothing earlier covers, dropping leftover pieces shorter than
    gap_fill_min_chars (see _fill_gaps).
    Non-fatal stages should catch their own exceptions (or be wrapped with
    _non_fatal) rather than propagating them.

    span_rules run in order on every detector's output *before*
    deduplication, so a span a rule drops never competes there.  Each rule is
    an object with ``apply(text, stage_results) -> SpanRuleResult``.  Spans a
    rule adds outrank every detector: any detector span overlapping one is
    dropped, the same way a lower-priority detector loses to a higher one.
    """

    stages: list  # callables: (text: str) -> list[dict]
    superset_stage_indices: frozenset = field(default_factory=frozenset)
    gap_fill_stage_indices: frozenset = field(default_factory=frozenset)
    gap_fill_min_chars: int = 0
    max_workers: int = 4
    span_rules: list = field(default_factory=list)

    def run(self, text: str) -> list[dict]:
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(_close_thread_connections(stage), text)
                for stage in self.stages
            ]
        stage_results = [fut.result() for fut in futures]

        rule_spans = []
        for rule in self.span_rules:
            outcome = rule.apply(text, stage_results)
            stage_results = outcome.stage_results
            rule_spans = _deduplicate_entities(rule_spans, outcome.added)

        combined = list(rule_spans)
        for i, results in enumerate(stage_results):
            if i in self.gap_fill_stage_indices:
                # Rule spans are already in combined, so they block here.
                combined = _fill_gaps(
                    combined, results, text, self.gap_fill_min_chars
                )
                continue
            if rule_spans:
                results = [
                    s for s in results if not _overlaps_any(s, rule_spans)
                ]
            combined = _deduplicate_entities(
                combined,
                results,
                allow_superset=(i in self.superset_stage_indices),
            )
        return combined


def build_default_pipeline(
    data_subject_name=None, data_subject_dob=None, *, presidio_snapshot=None
):
    """Build the standard four-extractor pipeline from singleton model managers.

    Priority order: Custom Presidio > SpanCat > Presidio > GLiNER > Gemma.
    Custom recognizers run first so admin-configured rules always override learned
    model predictions. SpanCat is omitted if no model is trained. Gemma is non-fatal,
    and its Operational Data fills only the text nothing else covers (gap-fill,
    at least GEMMA_GAP_FILL_MIN_CHARS per piece). The occurrence-report span rule (see span_rules) runs on every stage's output
    before deduplication, for the given data subject.
    Raises ValueError if no GLiNER model is available.

    One Presidio snapshot is acquired per pipeline (per document), so all
    Presidio stages of a document share identical recognizer config even if
    an admin edits custom recognizers mid-run. Pass ``presidio_snapshot`` to
    inject a substitute (any object with extract_custom / extract_third_party
    / extract_operational methods) in tests.
    """
    # Lazy imports — keep Django models and heavy extractor deps away from module load time
    from django.conf import settings

    from .extractors.gemma_extractor import extract_with_gemma
    from .extractors.gliner_extractor import extract_with_gliner
    from .extractors.presidio_provider import PresidioEngineProvider
    from .extractors.spancat_extractor import extract_with_spancat
    from .loader import GLiNERModelManager, SpanCatModelManager
    from .span_rules import build_occurrence_report_rule

    gliner_model = GLiNERModelManager.get_instance().get_model()
    if not gliner_model:
        raise ValueError("No GLiNER model available.")

    spancat_nlp = SpanCatModelManager.get_instance().get_model()

    snapshot = (
        presidio_snapshot
        or PresidioEngineProvider.get_instance().acquire_snapshot()
    )

    stages = []
    spancat_stage_index = None

    # Custom recognizers take absolute priority — runs before SpanCat so that
    # admin-configured patterns cannot be overridden by learned model predictions.
    stages.append(snapshot.extract_custom)

    if spancat_nlp:

        def _spancat_stage(text):
            return extract_with_spancat(spancat_nlp, text)

        spancat_stage_index = len(stages)
        stages.append(_spancat_stage)

    def _presidio_stage(text):
        return snapshot.extract_third_party(
            text
        ) + snapshot.extract_operational(text)

    stages.append(_presidio_stage)

    def _gliner_stage(text):
        return extract_with_gliner(gliner_model, text)

    stages.append(_gliner_stage)

    def _gemma_stage(text):
        return extract_with_gemma(text, data_subject_name, data_subject_dob)

    gemma_stage_index = len(stages)
    stages.append(_non_fatal(_gemma_stage))

    superset_stage_indices = (
        frozenset({spancat_stage_index})
        if spancat_stage_index is not None
        else frozenset()
    )
    return ExtractionPipeline(
        stages=stages,
        superset_stage_indices=superset_stage_indices,
        gap_fill_stage_indices=frozenset({gemma_stage_index}),
        gap_fill_min_chars=settings.GEMMA_GAP_FILL_MIN_CHARS,
        span_rules=[
            build_occurrence_report_rule(data_subject_name, data_subject_dob)
        ],
    )
