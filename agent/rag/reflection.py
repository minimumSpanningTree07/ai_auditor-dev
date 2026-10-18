from __future__ import annotations

import json
import re
from typing import Any

from litellm import completion

from agent.config import settings


def _build_reflection_prompt(
    question: str,
    context: str,
    answer: str,
) -> str:
    return f"""
You are evaluating an AI invoice-auditing RAG answer.

Evaluate the answer using the RAG Triad:

1. Context relevance:
   Does the retrieved context contain information relevant
   to answering the question?

2. Groundedness:
   Is the generated answer supported by the supplied context?
   Penalize claims that are invented or unsupported.

3. Question relevance:
   Does the answer actually answer the user's question?

Give each score from 0.0 to 1.0.

Return ONLY valid JSON in this exact structure:

{{
  "context_relevance": 0.0,
  "groundedness": 0.0,
  "question_relevance": 0.0,
  "overall_score": 0.0,
  "reason": "short explanation"
}}

QUESTION:
{question}

RETRIEVED CONTEXT:
{context}

GENERATED ANSWER:
{answer}
""".strip()


def _extract_json(text: str) -> dict[str, Any]:
    """
    Extract JSON even if the model accidentally surrounds it
    with markdown fences or additional whitespace.
    """

    text = text.strip()

    try:
        value = json.loads(text)

        if isinstance(value, dict):
            return value

    except json.JSONDecodeError:
        pass

    match = re.search(
        r"\{.*\}",
        text,
        flags=re.DOTALL,
    )

    if not match:
        raise ValueError(
            "Reflection model did not return JSON."
        )

    value = json.loads(match.group(0))

    if not isinstance(value, dict):
        raise ValueError(
            "Reflection response is not a JSON object."
        )

    return value


def _score(
    value: Any,
) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(
        0.0,
        min(1.0, score),
    )


def _evaluate(
    question: str,
    context: str,
    answer: str,
) -> dict[str, Any]:
    prompt = _build_reflection_prompt(
        question=question,
        context=context,
        answer=answer,
    )

    response = completion(
        model=settings.llm_model,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0.0,
        max_tokens=500,
    )

    content = response.choices[0].message.content

    if isinstance(content, list):
        content = "".join(
            str(
                item.get("text", "")
                if isinstance(item, dict)
                else item
            )
            for item in content
        )

    result = _extract_json(
        str(content or "")
    )

    context_relevance = _score(
        result.get("context_relevance")
    )

    groundedness = _score(
        result.get("groundedness")
    )

    question_relevance = _score(
        result.get("question_relevance")
    )

    supplied_overall = result.get(
        "overall_score"
    )

    if supplied_overall is None:
        overall_score = (
            context_relevance
            + groundedness
            + question_relevance
        ) / 3.0
    else:
        overall_score = _score(
            supplied_overall
        )

    return {
        "context_relevance": context_relevance,
        "groundedness": groundedness,
        "question_relevance": question_relevance,
        "overall_score": overall_score,
        "reason": str(
            result.get("reason") or ""
        ),
    }


def reflect(
    question: str,
    context: str,
    answer: str,
) -> dict[str, Any]:
    """
    Evaluate a generated RAG answer using the RAG Triad.
    """

    if not question.strip():
        return {
            "reflection_failed": True,
            "reflection_error": "Question is empty.",
        }

    if not context.strip():
        return {
            "reflection_failed": True,
            "reflection_error": "Context is empty.",
        }

    if not answer.strip():
        return {
            "reflection_failed": True,
            "reflection_error": "Answer is empty.",
        }

    try:
        result = _evaluate(
            question=question,
            context=context,
            answer=answer,
        )

        accepted = (
            result["overall_score"]
            >= settings.rag_score_threshold
        )

        return {
            **result,
            "reflection_failed": False,
            "rag_answer_accepted": accepted,
        }

    except Exception as exc:
        return {
            "reflection_failed": True,
            "rag_answer_accepted": False,
            "reflection_error": (
                f"Reflection failed: {exc}"
            ),
        }


def reflect_state(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Run reflection against the answer currently stored
    in workflow state.
    """

    question = str(
        state.get("rag_question") or ""
    )

    context = str(
        state.get("rag_context") or ""
    )

    answer = str(
        state.get("rag_answer") or ""
    )

    result = reflect(
        question=question,
        context=context,
        answer=answer,
    )

    updates: dict[str, Any] = {
        "rag_context_relevance": result.get(
            "context_relevance"
        ),
        "rag_groundedness": result.get(
            "groundedness"
        ),
        "rag_question_relevance": result.get(
            "question_relevance"
        ),
        "rag_score": result.get(
            "overall_score"
        ),
        "rag_answer_accepted": result.get(
            "rag_answer_accepted",
            False,
        ),
    }

    if result.get("reflection_failed"):
        updates["warnings"] = [
            *list(state.get("warnings") or []),
            result.get(
                "reflection_error",
                "RAG reflection failed.",
            ),
        ]

    return updates