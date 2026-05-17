"""
Presidio-based PII extractor for UK-specific patterns.

Uses Microsoft Presidio's AnalyzerEngine (regex / rule / checksum based)
to detect structured PII such as phone numbers, email addresses, and NHS
numbers entirely locally — no network calls are made.

extract_with_presidio()            → THIRD_PARTY structured PII
extract_operational_with_presidio() → OPERATIONAL structured refs (crime refs, collar numbers)
"""

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


def _load_custom_recognizers(entity_type, engine):
    """Register active custom recognizers of *entity_type* into *engine*. Returns extra entity names."""
    from presidio_analyzer import Pattern, PatternRecognizer

    from training.models import CustomRecognizer

    extra_entities = []
    for rec in CustomRecognizer.objects.filter(
        is_active=True, entity_type=entity_type
    ).prefetch_related("patterns", "deny_list"):
        patterns = [
            Pattern(name=p.name or f"p{i}", regex=p.regex, score=p.score)
            for i, p in enumerate(rec.patterns.all())
        ]
        deny_list = [item.value for item in rec.deny_list.all()]
        if not patterns and not deny_list:
            continue
        entity_name = f"CUSTOM_{rec.id.hex}"
        recognizer = PatternRecognizer(
            supported_entity=entity_name,
            patterns=patterns or None,
            deny_list=deny_list or None,
        )
        engine.registry.add_recognizer(recognizer)
        extra_entities.append(entity_name)
    return extra_entities


def _build_engine(base_recognizers, entity_type):
    """Return an (AnalyzerEngine, custom_entity_names) tuple.

    *base_recognizers* are registered first; active DB custom recognizers of
    *entity_type* are then appended.
    """
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    }
    nlp_engine = NlpEngineProvider(
        nlp_configuration=nlp_config
    ).create_engine()
    engine = AnalyzerEngine(nlp_engine=nlp_engine)

    for recognizer in base_recognizers:
        engine.registry.add_recognizer(recognizer)

    custom_entities = _load_custom_recognizers(entity_type, engine)
    return engine, custom_entities


def _build_analyzer():
    """Build a Presidio AnalyzerEngine configured with UK PII pattern recognisers."""
    from presidio_analyzer import Pattern, PatternRecognizer

    from training.models import CustomRecognizer

    return _build_engine(
        [
            PatternRecognizer(
                supported_entity="UK_POSTCODE",
                patterns=[
                    Pattern(
                        name="uk_postcode",
                        regex=r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b",
                        score=0.85,
                    )
                ],
            ),
            PatternRecognizer(
                supported_entity="UK_NI_NUMBER",
                patterns=[
                    Pattern(
                        name="uk_ni_number",
                        regex=r"\b(?!BG|GB|NK|KN|NT|TN|ZZ)[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b",
                        score=0.85,
                    )
                ],
            ),
        ],
        CustomRecognizer.EntityType.THIRD_PARTY,
    )


def _build_operational_analyzer():
    """Build a Presidio AnalyzerEngine configured with operational reference recognisers."""
    from presidio_analyzer import Pattern, PatternRecognizer

    from training.models import CustomRecognizer

    return _build_engine(
        [
            PatternRecognizer(
                supported_entity="UK_CRIME_REF",
                patterns=[
                    Pattern(
                        name="uk_crime_ref",
                        regex=r"\b\d{2}/\d{4,6}/\d{2}\b",
                        score=0.9,
                    )
                ],
            ),
            PatternRecognizer(
                supported_entity="UK_COLLAR_NUMBER",
                patterns=[
                    Pattern(
                        name="uk_collar_number",
                        regex=r"\b(?:PC|DC|DS|DI|DCI|DCS|PS|CI|PCSO)\s*\d{3,6}\b",
                        score=0.9,
                    )
                ],
            ),
        ],
        CustomRecognizer.EntityType.OPERATIONAL,
    )


# Singletons are (engine, custom_entity_names) tuples; None when not yet built.
_analyzer = None
_operational_analyzer = None


def _get_analyzer():
    """Return the singleton PII AnalyzerEngine tuple, creating it on first call."""
    global _analyzer
    if _analyzer is None:
        _analyzer = _build_analyzer()
    return _analyzer


def _get_operational_analyzer():
    """Return the singleton operational AnalyzerEngine tuple, creating it on first call."""
    global _operational_analyzer
    if _operational_analyzer is None:
        _operational_analyzer = _build_operational_analyzer()
    return _operational_analyzer


def extract_with_presidio(text):
    """
    Run Presidio analysis on *text* and return a list of PII entities.

    Returns a list of dicts with keys: text, label, start_char, end_char.
    All entities are mapped to THIRD_PARTY.
    """
    engine, custom_entities = _get_analyzer()
    entities = _PRESIDIO_ENTITIES + custom_entities
    results = engine.analyze(text=text, language="en", entities=entities)
    output = []
    for r in results:
        output.append(
            {
                "text": text[r.start : r.end],
                "label": "THIRD_PARTY",
                "start_char": r.start,
                "end_char": r.end,
            }
        )
    return output


def extract_operational_with_presidio(text):
    """
    Run Presidio analysis on *text* for structured OPERATIONAL references.

    Detects UK crime reference numbers (e.g. 42/12345/24) and collar numbers
    (e.g. PC 1234). Returns a list of dicts with keys: text, label, start_char,
    end_char. All entities are mapped to OPERATIONAL.
    """
    engine, custom_entities = _get_operational_analyzer()
    entities = _OPERATIONAL_ENTITIES + custom_entities
    results = engine.analyze(text=text, language="en", entities=entities)
    output = []
    for r in results:
        output.append(
            {
                "text": text[r.start : r.end],
                "label": "OPERATIONAL",
                "start_char": r.start,
                "end_char": r.end,
            }
        )
    return output
