import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

REDACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "redactions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "reason": {"type": "string"},
                    "redaction_type": {
                        "type": "string",
                        "enum": ["PII", "OP_DATA"],
                    },
                },
                "required": ["text", "reason", "redaction_type"],
            },
        }
    },
    "required": ["redactions"],
}

SYSTEM_PROMPT = """You are a data protection specialist reviewing documents for Subject
Access Requests (SARs) under UK GDPR and the Data Protection Act 2018.

Your task: identify text that must be redacted to protect third parties, while allowing
the data subject's own information to be disclosed.

Rules:
- Redact names, addresses, and identifying details of people who are NOT the data subject
- Redact operational information that would identify third-party officers or staff
- Do NOT redact information that is solely about the data subject
- Return only text that appears verbatim in the document"""


def extract_with_gemma(
    text: str, data_subject_name: str, data_subject_dob=None
) -> list[dict]:
    """
    Calls Ollama with a structured output schema. Returns a list of entity dicts
    with start_char/end_char resolved via string matching.

    Returns an empty list if OLLAMA_ENABLED is falsy or if the request fails.
    """
    if not settings.OLLAMA_ENABLED:
        return []

    context = f"Data subject: {data_subject_name}"
    if data_subject_dob:
        context += f", DOB: {data_subject_dob}"

    user_message = f"{context}\n\nDocument text:\n{text}"

    try:
        response = requests.post(
            f"{settings.OLLAMA_HOST}/api/chat",
            json={
                "model": settings.OLLAMA_MODEL,
                "stream": False,
                "format": REDACTION_SCHEMA,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            },
            timeout=120,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        if isinstance(content, str):
            content = json.loads(content)
        redactions_raw = content["redactions"]
    except Exception as exc:
        logger.warning("Gemma extractor failed: %s", exc)
        return []

    results = []
    for item in redactions_raw:
        phrase = item.get("text", "").strip()
        if not phrase:
            continue
        start = 0
        while True:
            idx = text.find(phrase, start)
            if idx == -1:
                break
            results.append(
                {
                    "text": phrase,
                    "start_char": idx,
                    "end_char": idx + len(phrase),
                    "label": item.get("redaction_type", "PII"),
                    "source": "LLM",
                }
            )
            start = idx + len(phrase)

    return results
