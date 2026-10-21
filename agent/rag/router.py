from __future__ import annotations

import re
from typing import Any

from agent.config import settings


# Only these read-only query categories are routed to SQL.
# Everything else goes through RAG.
_STRUCTURED_PATTERNS = [
    r"\b(invoice\s+number|invoice\s+no|invoice\s+id)\b",
    r"\b(how\s+many|count|list|show|find)\b.*\b(invoice|invoices)\b",
    r"\b(vendor|supplier)\b.*\b(invoice|invoices)\b",
    r"\b(invoice|invoices)\b.*\b(status|state)\b",
    r"\b(invoice|invoices)\b.*\b(total|amount|value)\b",
    r"\b(invoice|invoices)\b.*\b(discrepanc|mismatch|difference)\b",
    r"\b(invoice|invoices)\b.*\b(recommendation|decision)\b",
    r"\b(invoice|invoices)\b.*\b(po|purchase\s+order)\b",
    r"\b(invoice|invoices)\b.*\b(currency)\b",
    r"\b(invoice|invoices)\b.*\b(date|po|purchase\s+order|vendor|supplier)\b",
    r"^\s*what\s+(?:is|are|was|were)\b.*\b(total|amount|status|state|vendor|supplier|currency|purchase\s+order|po|invoice\s+number|line\s+items|sku|discrepanc(?:y|ies))\b",
    r"^\s*(?:how\s+many|count|list|show)\b.*\b(invoice|invoices|discrepanc(?:y|ies)|line\s+items)\b",
]


def _normalize(question: str) -> str:
    return " ".join(
        question.strip().lower().split()
    )


def classify_question(
    question: str,
) -> str:
    """
    Classify a question as:

        structured -> direct PostgreSQL query
        rag        -> Qdrant + generation

    This router only decides the query path.
    It does not execute SQL.
    """

    normalized = _normalize(question)

    if not normalized:
        return "rag"

    for pattern in _STRUCTURED_PATTERNS:
        if re.search(pattern, normalized):
            return "structured"

    return "rag"


def extract_invoice_id(
    question: str,
) -> str | None:
    """
    Extract an explicit invoice identifier when present.

    Examples:
        INV-1001
        INV-1001-CLEAN-V2
    """

    match = re.search(
        r"\bINV[-_][A-Za-z0-9_-]+\b",
        question,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(0)


def extract_rag_filters(
    question: str,
) -> dict[str, Any]:
    """
    Extract safe filters that can be applied to Qdrant retrieval.
    """

    invoice_id = extract_invoice_id(question)

    filters: dict[str, Any] = {}

    if invoice_id:
        filters["invoice_id"] = invoice_id

    return filters


def route_question(
    question: str,
) -> dict[str, Any]:
    """
    Route a user question to either the structured SQL path
    or the open-ended RAG path.
    """

    question = question.strip()

    intent = classify_question(question)

    if intent == "structured":
        return {
            "rag_intent": "structured",
            "rag_question": question,
            "rag_filters": extract_rag_filters(
                question
            ),
            "rag_route": "sql",
        }

    return {
        "rag_intent": "open_ended",
        "rag_question": question,
        "rag_filters": extract_rag_filters(
            question
        ),
        "rag_route": "rag",
        "rag_retry_count": 0,
        "rag_max_retries": settings.rag_max_retries,
    }


def route_state(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Route the question contained in workflow state.
    """

    question = str(
        state.get("rag_question")
        or state.get("question")
        or ""
    ).strip()

    result = route_question(question)

    return result