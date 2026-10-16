from __future__ import annotations

import json
from typing import Any

from agent.config import settings
from agent.services.cache import CacheError, cache


SUPPORTED_LANGUAGES = {
    "en",
    "eng",
    "english",
}


def _cache_key(text: str, source_language: str) -> str:
    import hashlib

    digest = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

    return (
        f"invoice:translation:"
        f"{source_language}:{digest}"
    )


def _detect_language(text: str) -> str:
    """
    Lightweight language detection.

    The LLM is used only when a reliable local result is not available.
    """

    try:
        from langdetect import detect

        return detect(text[:5000])

    except Exception:
        return "en"


def _translate_with_llm(
    text: str,
    source_language: str,
) -> str:
    """
    Translate invoice text to English using LiteLLM.

    LiteLLM is intentionally imported inside the function so the
    application can still start when an LLM provider is unavailable.
    """

    try:
        from litellm import completion
    except ImportError as exc:
        raise RuntimeError(
            "LiteLLM is required for invoice translation."
        ) from exc

    prompt = f"""
Translate the following invoice text into English.

Rules:
- Preserve invoice numbers exactly.
- Preserve PO numbers exactly.
- Preserve SKU/product codes exactly.
- Preserve dates, quantities and monetary values.
- Do not invent missing information.
- Keep the original line structure where possible.
- Return only the translated invoice text.

Source language: {source_language}

Invoice:
{text}
""".strip()

    response = completion(
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an invoice translation engine. "
                    "Translate faithfully without changing facts."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        max_tokens=settings.llm_max_tokens,
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "LLM returned an empty translation."
        )

    # Some providers may return a JSON string accidentally.
    # Only unwrap it when it is actually valid JSON.
    if isinstance(content, str):
        stripped = content.strip()

        try:
            parsed = json.loads(stripped)

            if isinstance(parsed, dict):
                translated = (
                    parsed.get("translation")
                    or parsed.get("translated_text")
                )

                if translated:
                    return str(translated)

            if isinstance(parsed, str):
                return parsed

        except json.JSONDecodeError:
            pass

        return stripped

    return str(content)


def translate_invoice(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Translate extracted invoice text to English when required.

    Original extraction is never overwritten.
    """

    text = state.get(
        "raw_extracted_text",
        "",
    )

    if not text:
        return {
            "translation_used": False,
            "translation_confidence": 0.0,
            "translation_error": (
                "No extracted text available for translation."
            ),
            "processing_status": "failed",
            "errors": [
                "Translation skipped because extracted text is empty."
            ],
        }

    source_language = (
        state.get("source_language")
        or _detect_language(text)
    )

    if source_language.lower() in SUPPORTED_LANGUAGES:
        return {
            "source_language": source_language,
            "translated_text": text,
            "translation_used": False,
            "translation_confidence": 1.0,
            "translation_error": None,
            "processing_status": "translation_complete",
        }

    key = _cache_key(
        text,
        source_language,
    )

    try:
        cached = cache.get(key)

        if isinstance(cached, dict):
            translated = cached.get(
                "translated_text"
            )

            if translated:
                return {
                    "source_language": source_language,
                    "translated_text": translated,
                    "translation_used": True,
                    "translation_confidence": cached.get(
                        "confidence",
                        0.95,
                    ),
                    "translation_error": None,
                    "processing_status": "translation_complete",
                }

    except CacheError:
        # Cache is optional; translation must continue.
        pass

    try:
        translated = _translate_with_llm(
            text,
            source_language,
        )

        confidence = 0.95

        try:
            cache.set(
                key,
                {
                    "translated_text": translated,
                    "confidence": confidence,
                },
            )
        except CacheError:
            pass

        return {
            "source_language": source_language,
            "translated_text": translated,
            "translation_used": True,
            "translation_confidence": confidence,
            "translation_error": None,
            "processing_status": "translation_complete",
        }

    except Exception as exc:
        return {
            "source_language": source_language,
            "translated_text": text,
            "translation_used": False,
            "translation_confidence": 0.0,
            "translation_error": str(exc),
            "processing_status": "failed",
            "errors": [
                f"Invoice translation failed: {exc}"
            ],
        }