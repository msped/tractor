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


def _build_analyzer():
    """Build a Presidio AnalyzerEngine configured with UK PII pattern recognisers."""
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer

    uk_postcode_pattern = Pattern(
        name="uk_postcode",
        regex=r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b",
        score=0.85,
    )
    uk_ni_pattern = Pattern(
        name="uk_ni_number",
        regex=r"\b(?!BG|GB|NK|KN|NT|TN|ZZ)[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b",
        score=0.85,
    )

    postcode_recognizer = PatternRecognizer(
        supported_entity="UK_POSTCODE",
        patterns=[uk_postcode_pattern],
    )
    ni_recognizer = PatternRecognizer(
        supported_entity="UK_NI_NUMBER",
        patterns=[uk_ni_pattern],
    )

    # Use en_core_web_sm (tiny model) instead of the default en_core_web_lg.
    # We only need Presidio for pattern-based PII — no NLP context needed.
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    }
    nlp_engine = NlpEngineProvider(
        nlp_configuration=nlp_config
    ).create_engine()

    engine = AnalyzerEngine(nlp_engine=nlp_engine)
    engine.registry.add_recognizer(postcode_recognizer)
    engine.registry.add_recognizer(ni_recognizer)
    return engine


def _build_operational_analyzer():
    """Build a Presidio AnalyzerEngine configured with operational reference recognisers (crime refs, collar numbers)."""
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer

    crime_ref_pattern = Pattern(
        name="uk_crime_ref",
        regex=r"\b\d{2}/\d{4,6}/\d{2}\b",
        score=0.9,
    )
    collar_number_pattern = Pattern(
        name="uk_collar_number",
        regex=r"\b(?:PC|DC|DS|DI|DCI|DCS|PS|CI|PCSO)\s*\d{3,6}\b",
        score=0.9,
    )

    crime_ref_recognizer = PatternRecognizer(
        supported_entity="UK_CRIME_REF",
        patterns=[crime_ref_pattern],
    )
    collar_number_recognizer = PatternRecognizer(
        supported_entity="UK_COLLAR_NUMBER",
        patterns=[collar_number_pattern],
    )

    from presidio_analyzer.nlp_engine import NlpEngineProvider

    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    }
    nlp_engine = NlpEngineProvider(
        nlp_configuration=nlp_config
    ).create_engine()

    engine = AnalyzerEngine(nlp_engine=nlp_engine)
    engine.registry.add_recognizer(crime_ref_recognizer)
    engine.registry.add_recognizer(collar_number_recognizer)
    return engine


_analyzer = None
_operational_analyzer = None


def _get_analyzer():
    """Return the singleton PII AnalyzerEngine, creating it on first call."""
    global _analyzer
    if _analyzer is None:
        _analyzer = _build_analyzer()
    return _analyzer


def _get_operational_analyzer():
    """Return the singleton operational AnalyzerEngine, creating it on first call."""
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
    analyzer = _get_analyzer()
    results = analyzer.analyze(
        text=text, language="en", entities=_PRESIDIO_ENTITIES
    )
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
    analyzer = _get_operational_analyzer()
    results = analyzer.analyze(
        text=text, language="en", entities=_OPERATIONAL_ENTITIES
    )
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
