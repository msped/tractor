import json
import logging
import re

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


def _build_norm_map(text: str) -> tuple[str, list[int]]:
    """
    Return (normalised_text, norm_to_orig) where normalised_text is lowercase
    with all whitespace runs collapsed to a single space, and norm_to_orig[i]
    is the original index of the i-th normalised character.
    """
    norm_chars = []
    norm_to_orig = []
    prev_was_space = False
    for i, c in enumerate(text):
        if c.isspace():
            if not prev_was_space:
                norm_chars.append(" ")
                norm_to_orig.append(i)
                prev_was_space = True
        else:
            norm_chars.append(c.lower())
            norm_to_orig.append(i)
            prev_was_space = False
    return "".join(norm_chars), norm_to_orig


def _find_phrase_in_chunk(
    phrase: str, chunk_text: str
) -> list[tuple[int, int]]:
    """
    Return a list of (start, end) offset tuples for all occurrences of phrase
    in chunk_text (chunk-local coordinates).

    Stage 1: exact str.find() — fast path, no overhead when Gemma output is clean.
    Stage 2: normalised fallback — lowercase + collapsed whitespace on both sides.
    When a normalised match is found, the returned offsets refer to the original
    chunk_text positions so the highlighted text always reflects the real document.
    """
    # Stage 1: exact match
    results = []
    start = 0
    while True:
        idx = chunk_text.find(phrase, start)
        if idx == -1:
            break
        results.append((idx, idx + len(phrase)))
        start = idx + len(phrase)
    if results:
        return results

    # Stage 2: normalised match
    norm_chunk, norm_to_orig = _build_norm_map(chunk_text)
    norm_phrase = re.sub(r"\s+", " ", phrase).lower()
    if not norm_phrase:
        return []

    start = 0
    while True:
        idx = norm_chunk.find(norm_phrase, start)
        if idx == -1:
            break
        orig_start = norm_to_orig[idx]
        orig_end = norm_to_orig[idx + len(norm_phrase) - 1] + 1
        results.append((orig_start, orig_end))
        start = idx + len(norm_phrase)

    return results


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
            if not content.strip():
                return []
            content = json.loads(content)
        redactions_raw = content["redactions"]
    except Exception as exc:
        logger.warning("Gemma extractor failed: %s", exc)
        return []

    logger.debug("Gemma raw redactions: %s", redactions_raw)

    results = []
    for item in redactions_raw:
        phrase = item.get("text", "").strip()
        if not phrase:
            continue
        matches = _find_phrase_in_chunk(phrase, chunk_text)
        if not matches:
            logger.warning(
                "Gemma returned phrase not found in chunk: %r", phrase
            )
            continue
        for start, end in matches:
            results.append(
                {
                    "text": chunk_text[start:end],
                    "start_char": chunk_offset + start,
                    "end_char": chunk_offset + end,
                    "label": item.get("redaction_type", "PII"),
                    "source": "LLM",
                }
            )

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
