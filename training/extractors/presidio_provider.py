"""
Presidio analyzer lifecycle: per-document snapshots with DB-fingerprint freshness.

Uses Microsoft Presidio's AnalyzerEngine (regex / rule / checksum based)
to detect structured PII such as phone numbers, email addresses, and NHS
numbers entirely locally — no network calls are made.

Freshness is comparison-based, not notification-based: ``acquire_snapshot()``
fingerprints the custom-recognizer tables (a content hash over three tiny
PK-ordered SELECTs) and swaps in a new immutable ``PresidioSnapshot`` when the
config changed. Correctness never depends on a signal firing, so admin edits
to custom recognizers take effect on the next document in every process —
including qcluster workers.

A snapshot is acquired once per document (in ``build_default_pipeline``) and
never mutated after publication, so all pipeline stages of one document see
identical recognizer config and in-flight ``analyze()`` calls can never
observe a half-rebuilt registry.
"""

import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)

_PRESIDIO_ENTITIES = [
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "UK_NHS",
    "UK_POSTCODE",
    "UK_NI_NUMBER",
]

_OPERATIONAL_ENTITIES = [
    "UK_CRIME_REF",
    "UK_COLLAR_NUMBER",
]

# Built-in UK pattern recognisers as plain data: (entity, name, regex, score).
_BUILTIN_THIRD_PARTY_PATTERNS = (
    (
        "UK_POSTCODE",
        "uk_postcode",
        r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b",
        0.85,
    ),
    (
        "UK_NI_NUMBER",
        "uk_ni_number",
        r"\b(?!BG|GB|NK|KN|NT|TN|ZZ)[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b",
        0.85,
    ),
)

_BUILTIN_OPERATIONAL_PATTERNS = (
    (
        "UK_CRIME_REF",
        "uk_crime_ref",
        r"\b\d{2}/\d{4,6}/\d{2}\b",
        0.9,
    ),
    (
        "UK_COLLAR_NUMBER",
        "uk_collar_number",
        r"\b(?:PC|DC|DS|DI|DCI|DCS|PS|CI|PCSO)\s*\d{3,6}\b",
        0.9,
    ),
)

# Engine configs: key -> (builtin patterns, custom entity_type, nlp context).
# The nlp context groups engines that run sequentially on the same pipeline
# thread so they can share one spaCy NlpEngine: the two builtin engines run
# inside one stage, the two custom-only engines inside another. Engines on
# different pipeline threads deliberately do NOT share a spaCy instance
# (Language objects are not guaranteed thread-safe for concurrent calls).
_ENGINE_CONFIGS = {
    "third_party": (_BUILTIN_THIRD_PARTY_PATTERNS, "THIRD_PARTY", "builtin"),
    "operational": (_BUILTIN_OPERATIONAL_PATTERNS, "OPERATIONAL", "builtin"),
    "custom_third_party": ((), "THIRD_PARTY", "custom"),
    "custom_operational": ((), "OPERATIONAL", "custom"),
}


@dataclass(frozen=True)
class RecognizerSpec:
    """Plain-data image of one active CustomRecognizer + children, captured
    at snapshot time so engine building never touches the DB."""

    id_hex: str
    entity_type: str
    patterns: tuple  # ((name, regex, score), ...)
    deny_list: tuple  # (value, ...)


def _load_specs_and_fingerprint():
    """Three PK-ordered SELECTs over the recognizer tables ->
    (sha256 fingerprint, tuple[RecognizerSpec]).

    Content hash, not timestamps or counts: an in-place regex edit via
    ``queryset.update()`` changes neither ``updated_at`` nor row counts, but
    it does change row content, so hashing content is correct on any write
    path. No presidio/spacy imports here — only Django models.
    """
    from training.models import (
        CustomDenyListItem,
        CustomPattern,
        CustomRecognizer,
    )

    recognizers = list(
        CustomRecognizer.objects.filter(is_active=True)
        .order_by("pk")
        .values_list("id", "entity_type")
    )
    active_ids = [rec_id for rec_id, _ in recognizers]
    patterns = list(
        CustomPattern.objects.filter(recognizer_id__in=active_ids)
        .order_by("pk")
        .values_list("recognizer_id", "name", "regex", "score")
    )
    deny_items = list(
        CustomDenyListItem.objects.filter(recognizer_id__in=active_ids)
        .order_by("pk")
        .values_list("recognizer_id", "value")
    )

    fingerprint = hashlib.sha256(
        repr((recognizers, patterns, deny_items)).encode()
    ).hexdigest()

    patterns_by_rec = defaultdict(list)
    for rec_id, name, regex, score in patterns:
        patterns_by_rec[rec_id].append((name, regex, score))
    deny_by_rec = defaultdict(list)
    for rec_id, value in deny_items:
        deny_by_rec[rec_id].append(value)

    specs = tuple(
        RecognizerSpec(
            id_hex=rec_id.hex,
            entity_type=entity_type,
            patterns=tuple(patterns_by_rec[rec_id]),
            deny_list=tuple(deny_by_rec[rec_id]),
        )
        for rec_id, entity_type in recognizers
        if patterns_by_rec[rec_id] or deny_by_rec[rec_id]
    )
    return fingerprint, specs


class PresidioSnapshot:
    """Immutable view of recognizer config + lazily-built engines.

    Never mutated after publication — safe for concurrent analyze() from
    pipeline threads; a snapshot handed to a document stays coherent even if
    the config changes mid-run. Engines are built lazily under a
    double-checked lock, so exactly one build happens per engine config
    under contention.
    """

    def __init__(self, fingerprint, specs):
        self.fingerprint = fingerprint
        self._specs = specs
        self._build_lock = Lock()
        self._engines = {}  # key -> (AnalyzerEngine, custom_entity_names)
        self._nlp_engines = {}  # nlp context -> NlpEngine

    def _get_nlp_engine(self, context):
        """Return the shared spaCy NlpEngine for *context*. Called only
        while holding ``_build_lock``."""
        nlp_engine = self._nlp_engines.get(context)
        if nlp_engine is None:
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            nlp_config = {
                "nlp_engine_name": "spacy",
                "models": [
                    {"lang_code": "en", "model_name": "en_core_web_sm"}
                ],
            }
            nlp_engine = NlpEngineProvider(
                nlp_configuration=nlp_config
            ).create_engine()
            self._nlp_engines[context] = nlp_engine
        return nlp_engine

    def _build_engine(self, key):
        """Build the (engine, custom_entity_names) tuple for *key*. Called
        only while holding ``_build_lock``."""
        from presidio_analyzer import (
            AnalyzerEngine,
            Pattern,
            PatternRecognizer,
        )

        builtin_patterns, entity_type, context = _ENGINE_CONFIGS[key]

        engine = AnalyzerEngine(nlp_engine=self._get_nlp_engine(context))

        for entity, name, regex, score in builtin_patterns:
            engine.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity=entity,
                    patterns=[Pattern(name=name, regex=regex, score=score)],
                )
            )

        custom_entities = []
        for spec in self._specs:
            if spec.entity_type != entity_type:
                continue
            patterns = [
                Pattern(name=name or f"p{i}", regex=regex, score=score)
                for i, (name, regex, score) in enumerate(spec.patterns)
            ]
            entity_name = f"CUSTOM_{spec.id_hex}"
            engine.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity=entity_name,
                    patterns=patterns or None,
                    deny_list=list(spec.deny_list) or None,
                )
            )
            custom_entities.append(entity_name)
        return engine, custom_entities

    def _get_engine(self, key):
        engine = self._engines.get(key)
        if engine is None:
            with self._build_lock:
                engine = self._engines.get(key)
                if engine is None:
                    engine = self._build_engine(key)
                    self._engines[key] = engine
        return engine

    def _analyze(self, key, entities, text, label):
        engine, custom_entities = self._get_engine(key)
        results = engine.analyze(
            text=text, language="en", entities=entities + custom_entities
        )
        return [
            {
                "text": text[r.start : r.end],
                "label": label,
                "start_char": r.start,
                "end_char": r.end,
            }
            for r in results
        ]

    def _has_custom_specs(self, entity_type):
        return any(spec.entity_type == entity_type for spec in self._specs)

    def extract_third_party(self, text):
        """Built-in UK PII patterns + custom THIRD_PARTY recognizers.

        Returns a list of dicts with keys: text, label, start_char, end_char.
        All entities are mapped to THIRD_PARTY.
        """
        return self._analyze(
            "third_party", _PRESIDIO_ENTITIES, text, "THIRD_PARTY"
        )

    def extract_operational(self, text):
        """Built-in structured OPERATIONAL refs (crime refs, collar numbers)
        + custom OPERATIONAL recognizers.

        Returns a list of dicts with keys: text, label, start_char, end_char.
        All entities are mapped to OPERATIONAL.
        """
        return self._analyze(
            "operational", _OPERATIONAL_ENTITIES, text, "OPERATIONAL"
        )

    def extract_custom(self, text):
        """Run ONLY the admin-configured custom recognizers against *text*.

        Returns THIRD_PARTY and OPERATIONAL matches from custom recognizers,
        with no built-in patterns. Used as the highest-priority pipeline stage
        so explicit admin rules always override learned model predictions.
        Short-circuits without building any engine when no custom recognizers
        are configured.
        """
        output = []
        for key, entity_type, label in (
            ("custom_third_party", "THIRD_PARTY", "THIRD_PARTY"),
            ("custom_operational", "OPERATIONAL", "OPERATIONAL"),
        ):
            if not self._has_custom_specs(entity_type):
                continue
            output.extend(self._analyze(key, [], text, label))
        return output


class PresidioEngineProvider:
    """Process-wide holder of the current PresidioSnapshot.

    ``acquire_snapshot()`` is THE per-document call: it fingerprints the DB
    config, swaps in a new snapshot if it changed, and returns the current
    one. Swap, never mutate — old snapshots are GC'd when their documents
    drain.
    """

    _instance = None
    _instance_lock = Lock()

    def __init__(self):
        self._lock = Lock()
        self._snapshot = None

    @classmethod
    def get_instance(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def acquire_snapshot(self):
        fingerprint, specs = _load_specs_and_fingerprint()
        with self._lock:
            if (
                self._snapshot is None
                or self._snapshot.fingerprint != fingerprint
            ):
                logger.info(
                    "Building new Presidio snapshot (fingerprint %s).",
                    fingerprint[:12],
                )
                self._snapshot = PresidioSnapshot(fingerprint, specs)
            return self._snapshot

    @classmethod
    def reset_for_tests(cls):
        with cls._instance_lock:
            cls._instance = None
