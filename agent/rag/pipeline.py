from __future__ import annotations

from typing import Any

from agent.config import settings
from agent.rag.retrieval import retrieve
from agent.rag.augmentation import augment
from agent.rag.generation import generate
from agent.rag.reflection import reflect


def run_rag(
    question: str,
    invoice_id: str | None = None,
) -> dict[str, Any]:

    max_retries = int(settings.rag_max_retries)

    last_result: dict[str, Any] = {
        "question": question,
        "invoice_id": invoice_id,
        "documents": [],
        "context": "",
        "answer": "",
        "reflection": {},
        "accepted": False,
        "retry_count": 0,
    }

    for attempt in range(max_retries + 1):

        # Retrieval
        documents = retrieve(
            question=question,
            invoice_id=invoice_id,
        )

        # Augmentation
        augmented = augment(documents)

        context = augmented.get("context", "")

        # Insufficient context
        if not augmented.get("sufficient", False):
            last_result = {
                **last_result,
                "documents": documents,
                "context": context,
                "answer": "",
                "reflection": {
                    "overall_score": 0.0,
                    "accepted": False,
                    "reason": "Retrieved context was insufficient.",
                },
                "accepted": False,
                "retry_count": attempt,
            }

            if attempt < max_retries:
                continue

            break

        # Generation
        answer = generate(
            question=question,
            context=context,
        )

        # Reflection
        reflection = reflect(
            question=question,
            context=context,
            answer=answer,
        )

        accepted = bool(reflection.get("accepted", False))

        last_result = {
            "question": question,
            "invoice_id": invoice_id,
            "documents": documents,
            "context": context,
            "answer": answer,
            "reflection": reflection,
            "accepted": accepted,
            "retry_count": attempt,
        }

        # Accepted answer
        if accepted:
            break

        # Otherwise retry

    return last_result