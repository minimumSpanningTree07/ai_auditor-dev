from __future__ import annotations

import re
from typing import Any

from agent.rag.augmentation import augment_context
from agent.rag.generation import generate_answer
from agent.rag.reflection import reflect_answer
from agent.rag.retrieval import retrieve_documents


STRUCTURED_TERMS = {
    "invoice",
    "invoice number",
    "vendor",
    "supplier",
    "purchase order",
    "po",
    "sku",
    "quantity",
    "price",
    "amount",
    "tax",
    "subtotal",
    "total",
    "currency",
    "discrepancy",
    "validation",
    "status",
    "recommendation",
}


def classify_query(question: str) -> str:
    normalized = question.lower().strip()

    if not normalized:
        return "unknown"

    if any(
        term in normalized
        for term in STRUCTURED_TERMS
    ):
        return "structured"

    return "semantic"


def _extract_invoice_id(question: str) -> str | None:
    match = re.search(
        r"\bINV[-_ ]?\d+\b",
        question,
        re.IGNORECASE,
    )

    return match.group(0) if match else None


def route_question(
    question: str,
) -> dict[str, Any]:
    intent = classify_query(question)

    if intent == "unknown":
        return {
            "query_intent": "unknown",
            "retrieved_documents": [],
            "augmented_context": "",
            "rag_answer": (
                "Please provide a question about an invoice, "
                "vendor, purchase order, validation result, "
                "discrepancy, or related audit information."
            ),
            "rag_context_relevance": 0.0,
            "rag_answer_groundedness": 0.0,
            "rag_question_relevance": 0.0,
            "rag_triad_score": 0.0,
        }

    documents = retrieve_documents(
        question=question,
    )

    invoice_id = _extract_invoice_id(question)

    if invoice_id:
        matching = [
            document
            for document in documents
            if str(
                document.get("invoice_number") or ""
            ).lower()
            == invoice_id.lower()
        ]

        if matching:
            documents = matching

    context = augment_context(
        question,
        documents,
    )

    generated = generate_answer(
        question,
        context,
    )

    reflection = reflect_answer(
        question,
        context,
        generated.get("rag_answer", ""),
    )

    return {
        "query_intent": intent,
        "query_filters": {
            "invoice_number": invoice_id,
        },
        "retrieved_documents": documents,
        "augmented_context": context,
        **generated,
        **reflection,
    }


def answer_question(
    state: dict[str, Any],
) -> dict[str, Any]:
    return route_question(
        str(state.get("question") or "")
    )