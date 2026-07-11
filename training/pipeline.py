import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


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
                and s < ent["end_char"]
                and e > ent["start_char"]
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
                if s < ent["end_char"] and e > ent["start_char"]
            ]

        if not other_overlap_indices:
            combined.append(sec_ent)
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


@dataclass
class ExtractionPipeline:
    """
    Runs extractors concurrently and deduplicates in priority order.

    stages[0] has highest priority; later stages are dropped on overlap.
    superset_stage_indices marks which stages may extend earlier predictions via
    the superset replacement rule (see _deduplicate_entities).
    Non-fatal stages should catch their own exceptions (or be wrapped with
    _non_fatal) rather than propagating them.
    """

    stages: list  # callables: (text: str) -> list[dict]
    superset_stage_indices: frozenset = field(default_factory=frozenset)
    max_workers: int = 4

    def run(self, text: str) -> list[dict]:
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(_close_thread_connections(stage), text)
                for stage in self.stages
            ]
        stage_results = [fut.result() for fut in futures]

        combined = []
        for i, results in enumerate(stage_results):
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
    model predictions. SpanCat is omitted if no model is trained. Gemma is non-fatal.
    Raises ValueError if no GLiNER model is available.

    One Presidio snapshot is acquired per pipeline (per document), so all
    Presidio stages of a document share identical recognizer config even if
    an admin edits custom recognizers mid-run. Pass ``presidio_snapshot`` to
    inject a substitute (any object with extract_custom / extract_third_party
    / extract_operational methods) in tests.
    """
    # Lazy imports — keep Django models and heavy extractor deps away from module load time
    from .extractors.gemma_extractor import extract_with_gemma
    from .extractors.gliner_extractor import extract_with_gliner
    from .extractors.presidio_provider import PresidioEngineProvider
    from .extractors.spancat_extractor import extract_with_spancat
    from .loader import GLiNERModelManager, SpanCatModelManager

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

    stages.append(_non_fatal(_gemma_stage))

    superset_stage_indices = (
        frozenset({spancat_stage_index})
        if spancat_stage_index is not None
        else frozenset()
    )
    return ExtractionPipeline(
        stages=stages, superset_stage_indices=superset_stage_indices
    )
