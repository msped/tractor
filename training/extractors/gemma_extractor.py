import json
import logging

import requests
from django.conf import settings

from training.models import LLMPromptSettings

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


def _chunk_text(
    text: str, chunk_size: int, overlap: int
) -> list[tuple[str, int]]:
    """Split text into overlapping chunks, returning (chunk_text, offset) pairs."""
    if len(text) <= chunk_size:
        return [(text, 0)]

    chunks = []
    step = chunk_size - overlap
    start = 0
    while start < len(text):
        chunks.append((text[start : start + chunk_size], start))
        start += step
    return chunks


def _call_ollama(
    chunk_text: str, chunk_offset: int, user_context: str, system_prompt: str
) -> list[dict]:
    """
    Send one chunk to Ollama and return spans with offsets corrected to the
    full document's coordinate space. Returns an empty list on failure.
    """
    user_message = f"{user_context}\n\nDocument text:\n{chunk_text}"

    try:
        response = requests.post(
            f"{settings.OLLAMA_HOST}/api/chat",
            json={
                "model": settings.OLLAMA_MODEL,
                "stream": False,
                "format": REDACTION_SCHEMA,
                "messages": [
                    {"role": "system", "content": system_prompt},
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
            idx = chunk_text.find(phrase, start)
            if idx == -1:
                break
            results.append(
                {
                    "text": phrase,
                    "start_char": chunk_offset + idx,
                    "end_char": chunk_offset + idx + len(phrase),
                    "label": item.get("redaction_type", "PII"),
                    "source": "LLM",
                }
            )
            start = idx + len(phrase)

    return results


def extract_with_gemma(
    text: str, data_subject_name: str, data_subject_dob=None
) -> list[dict]:
    """
    Calls Ollama with a structured output schema. Splits large documents into
    overlapping chunks so no content exceeds the model's context limit. Returns
    a list of entity dicts with start_char/end_char in full-document coordinates.

    Returns an empty list if OLLAMA_ENABLED is falsy or if all requests fail.
    """
    if not settings.OLLAMA_ENABLED:
        return []

    chunk_size = getattr(settings, "OLLAMA_CHUNK_SIZE", 4000)
    overlap = getattr(settings, "OLLAMA_CHUNK_OVERLAP", 200)

    user_context = f"Data subject: {data_subject_name}"
    if data_subject_dob:
        user_context += f", DOB: {data_subject_dob}"

    system_prompt = LLMPromptSettings.get().system_prompt
    chunks = _chunk_text(text, chunk_size, overlap)

    seen = set()
    results = []
    for chunk_text, chunk_offset in chunks:
        for span in _call_ollama(
            chunk_text, chunk_offset, user_context, system_prompt
        ):
            key = (span["start_char"], span["end_char"])
            if key not in seen:
                seen.add(key)
                results.append(span)

    return results
