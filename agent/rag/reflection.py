from __future__ import annotations

import re
from typing import Any


def _tokenize(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"\b[a-zA-Z0-9_-]+\b", text)
        if len(token) > 2
    }


def _groundedness(
    answer: str,
    context: str,
) -> float:
    answer_tokens = _tokenize(answer)
    context_tokens = _tokenize(context)

    if not answer_tokens:
        return 0.0

    if not context_tokens:
        return 0.0

    overlap = answer_tokens.intersection(context_tokens)

    return min(
        1.0,
        len(overlap) / max(len(answer_tokens), 1),
    )


def _question_relevance(
    question: str,
    answer: str,
) -> float:
    question_tokens = _tokenize(question)
    answer_tokens = _tokenize(answer)

    if not question_tokens or not answer_tokens:
        return 0.0

    overlap = question_tokens.intersection(answer_tokens)

    return min(
        1.0,
        len(overlap) / max(len(question_tokens), 1),
    )


def reflect_answer(
    question: str,
    context: str,
    answer: str,
) -> dict[str, Any]:
    groundedness = _groundedness(
        answer,
        context,
    )

    relevance = _question_relevance(
        question,
        answer,
    )

    context_relevance = (
        1.0
        if context.strip()
        else 0.0
    )

    triad_score = (
        context_relevance
        + groundedness
        + relevance
    ) / 3.0

    return {
        "rag_context_relevance": round(
            context_relevance,
            4,
        ),
        "rag_answer_groundedness": round(
            groundedness,
            4,
        ),
        "rag_question_relevance": round(
            relevance,
            4,
        ),
        "rag_triad_score": round(
            triad_score,
            4,
        ),
    }


def reflection_node(
    state: dict[str, Any],
) -> dict[str, Any]:
    return reflect_answer(
        question=str(
            state.get("question") or ""
        ),
        context=str(
            state.get("augmented_context") or ""
        ),
        answer=str(
            state.get("rag_answer") or ""
        ),
    )