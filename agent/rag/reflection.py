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
You are evaluating an AI-generated answer for an invoice-auditing RAG system.

Evaluate the answer using the RAG Triad.

1. Context relevance:
   Does the retrieved context contain information relevant
   to answering the question?

2. Groundedness:
   Is the generated answer supported by the supplied context?
   Penalize claims that are invented or unsupported.

3. Question relevance:
   Does the answer directly answer the user's question?

Give each score from 0.0 to 1.0.

Return ONLY valid JSON with exactly these fields:

{{
  "context_relevance": 0.0,
  "groundedness": 0.0,
  "question_relevance": 0.0,
  "reason": "short explanation"
}}

Do NOT provide an overall_score.
The application will calculate it deterministically.

QUESTION:
{question}

RETRIEVED CONTEXT:
{context}

GENERATED ANSWER:
{answer}
""".strip()


def _extract_json(text: str) -> dict[str, Any]:
    """
    Extract a JSON object from the model response.
    Handles plain JSON and markdown/code-fence responses.
    """
    text = text.strip()

    # First try the entire response.
    try:
        value = json.loads(text)

        if isinstance(value, dict):
            return value

    except json.JSONDecodeError:
        pass

    # Then find the first JSON object.
    match = re.search(
        r"\{.*\}",
        text,
        flags=re.DOTALL,
    )

    if not match:
        raise ValueError(
            "Reflection model did not return valid JSON."
        )

    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON returned by reflection model: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise ValueError(
            "Reflection response is not a JSON object."
        )

    return value


def _score(value: Any) -> float:
    """
    Normalize a score to the range [0.0, 1.0].
    """
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

    # Nova responses can sometimes contain structured content.
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

    # IMPORTANT:
    # Never trust the LLM to calculate the final score.
    overall_score = (
        context_relevance
        + groundedness
        + question_relevance
    ) / 3.0

    return {
        "context_relevance": context_relevance,
        "groundedness": groundedness,
        "question_relevance": question_relevance,
        "overall_score": round(overall_score, 4),
        "reason": str(
            result.get("reason") or ""
        ).strip(),
    }


def reflect(
    question: str,
    context: str,
    answer: str,
) -> dict[str, Any]:
    """
    Evaluate a generated RAG answer using the RAG Triad.

    Acceptance:
        overall_score > rag_score_threshold
    """

    if not question.strip():
        return {
            "context_relevance": 0.0,
            "groundedness": 0.0,
            "question_relevance": 0.0,
            "overall_score": 0.0,
            "reason": "Question is empty.",
            "accepted": False,
            "rag_answer_accepted": False,
            "reflection_failed": True,
            "reflection_error": "Question is empty.",
        }

    if not context.strip():
        return {
            "context_relevance": 0.0,
            "groundedness": 0.0,
            "question_relevance": 0.0,
            "overall_score": 0.0,
            "reason": "Context is empty.",
            "accepted": False,
            "rag_answer_accepted": False,
            "reflection_failed": True,
            "reflection_error": "Context is empty.",
        }

    if not answer.strip():
        return {
            "context_relevance": 0.0,
            "groundedness": 0.0,
            "question_relevance": 0.0,
            "overall_score": 0.0,
            "reason": "Answer is empty.",
            "accepted": False,
            "rag_answer_accepted": False,
            "reflection_failed": True,
            "reflection_error": "Answer is empty.",
        }

    try:
        result = _evaluate(
            question=question,
            context=context,
            answer=answer,
        )

        threshold = float(
            settings.rag_score_threshold
        )

        accepted = (
            result["overall_score"] > threshold
        )

        return {
            **result,
            "accepted": accepted,
            "rag_answer_accepted": accepted,
            "reflection_failed": False,
        }

    except Exception as exc:
        error = f"Reflection failed: {exc}"

        return {
            "context_relevance": 0.0,
            "groundedness": 0.0,
            "question_relevance": 0.0,
            "overall_score": 0.0,
            "reason": error,
            "accepted": False,
            "rag_answer_accepted": False,
            "reflection_failed": True,
            "reflection_error": error,
        }


def reflect_state(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    LangGraph-compatible reflection node.
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
            "accepted",
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
