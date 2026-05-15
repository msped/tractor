import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _deduplicate_entities(primary_entities, secondary_entities):
    """Keep primary entities; add secondary only where no overlap with primary exists."""
    combined = list(primary_entities)
    for sec_ent in secondary_entities:
        overlaps = any(
            sec_ent["start_char"] < pri_ent["end_char"]
            and sec_ent["end_char"] > pri_ent["start_char"]
            for pri_ent in primary_entities
        )
        if not overlaps:
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
    Non-fatal stages should catch their own exceptions (or be wrapped with
    _non_fatal) rather than propagating them.
    """

    stages: list  # callables: (text: str) -> list[dict]
    max_workers: int = 4

    def run(self, text: str) -> list[dict]:
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(stage, text) for stage in self.stages]
        stage_results = [fut.result() for fut in futures]

        combined = []
        for results in stage_results:
            combined = _deduplicate_entities(combined, results)
        return combined


def build_default_pipeline(data_subject_name=None, data_subject_dob=None):
    """Build the standard four-extractor pipeline from singleton model managers.

    Priority order: SpanCat > GLiNER > Presidio > Gemma.
    SpanCat is omitted if no model is trained. Gemma is non-fatal.
    Raises ValueError if no GLiNER model is available.
    """
    # Lazy imports — keep Django models and heavy extractor deps away from module load time
    from .extractors.gemma_extractor import extract_with_gemma
    from .extractors.gliner_extractor import extract_with_gliner
    from .extractors.presidio_extractor import (
        extract_operational_with_presidio,
        extract_with_presidio,
    )
    from .extractors.spancat_extractor import extract_with_spancat
    from .loader import GLiNERModelManager, SpanCatModelManager

    gliner_model = GLiNERModelManager.get_instance().get_model()
    if not gliner_model:
        raise ValueError("No GLiNER model available.")

    spancat_nlp = SpanCatModelManager.get_instance().get_model()

    stages = []

    if spancat_nlp:

        def _spancat_stage(text):
            return extract_with_spancat(spancat_nlp, text)

        stages.append(_spancat_stage)

    def _gliner_stage(text):
        return extract_with_gliner(gliner_model, text)

    stages.append(_gliner_stage)

    def _presidio_stage(text):
        return extract_with_presidio(text) + extract_operational_with_presidio(
            text
        )

    stages.append(_presidio_stage)

    def _gemma_stage(text):
        return extract_with_gemma(text, data_subject_name, data_subject_dob)

    stages.append(_non_fatal(_gemma_stage))

    return ExtractionPipeline(stages=stages)
