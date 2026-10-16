from __future__ import annotations

import hashlib
import json
from typing import Any

import litellm

from agent.config import settings
from agent.services.cache import cache


def _cache_key(question: str, context: str) -> str:
    value = f"{question}\n{context}"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"rag:answer:{digest}"


def _build_prompt(
    question: str,
    context: str,
) -> str:
    return f"""
You are an AI invoice audit assistant.

Answer the user's question using ONLY the retrieved context.

Rules:
- Do not invent facts.
- If the context is insufficient, explicitly say so.
- Prefer precise invoice numbers, vendor names, PO numbers,
  validation statuses, discrepancies, and recommendations.
- Keep the answer concise.
- Explain the evidence supporting the answer.

USER QUESTION:
{question}

RETRIEVED CONTEXT:
{context}
""".strip()


def generate_answer(
    question: str,
    context: str,
) -> dict[str, Any]:
    if not question.strip():
        return {
            "rag_answer": "",
            "rag_question_relevance": 0.0,
            "rag_answer_groundedness": 0.0,
        }

    key = _cache_key(question, context)

    try:
        cached = cache.get(key)

        if cached:
            return {
                "rag_answer": cached,
                "rag_question_relevance": 1.0,
                "rag_answer_groundedness": 1.0,
            }
    except Exception:
        pass

    prompt = _build_prompt(question, context)

    try:
        response = litellm.completion(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a factual enterprise "
                        "invoice auditing assistant."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        content = response.choices[0].message.content

        if isinstance(content, list):
            content = "".join(
                str(item.get("text", ""))
                if isinstance(item, dict)
                else str(item)
                for item in content
            )

        answer = str(content or "").strip()

        if not answer:
            raise ValueError("LLM returned an empty answer")

        try:
            cache.set(
                key,
                answer,
                ttl=settings.redis_ttl,
            )
        except Exception:
            pass

        return {
            "rag_answer": answer,
            "rag_question_relevance": 1.0,
            "rag_answer_groundedness": 1.0
            if context.strip()
            else 0.0,
        }

    except Exception as exc:
        return {
            "rag_answer": (
                "Unable to generate an answer from the "
                f"retrieved context: {exc}"
            ),
            "rag_question_relevance": 0.0,
            "rag_answer_groundedness": 0.0,
            "errors": [
                f"RAG generation failed: {exc}",
            ],
        }