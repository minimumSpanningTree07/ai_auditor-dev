from __future__ import annotations

from typing import Any


def _deduplicate(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove duplicate chunks while preserving relevance order."""

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []

    for document in documents:
        text = str(document.get("text") or "").strip()

        if not text:
            continue

        # Normalize whitespace for duplicate detection.
        key = " ".join(text.split())

        if key in seen:
            continue

        seen.add(key)
        unique.append(document)

    return unique


def _filter_by_score(
    documents: list[dict[str, Any]],
    threshold: float,
) -> list[dict[str, Any]]:
    """Keep only chunks meeting the configured relevance threshold."""

    return [
        document
        for document in documents
        if float(document.get("score", 0.0)) >= threshold
    ]


def _rank_documents(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Ensure highest-scoring documents appear first."""

    return sorted(
        documents,
        key=lambda document: float(
            document.get("score", 0.0)
        ),
        reverse=True,
    )


def _build_context(
    documents: list[dict[str, Any]],
) -> str:
    """Build the context passed to the RAG generation model."""

    sections: list[str] = []

    for index, document in enumerate(
        documents,
        start=1,
    ):
        score = float(
            document.get("score", 0.0)
        )

        invoice_number = (
            document.get("invoice_number")
            or "unknown"
        )

        vendor = (
            document.get("vendor_name")
            or "unknown"
        )

        sections.append(
            (
                f"--- Context {index} ---\n"
                f"Relevance Score: {score:.4f}\n"
                f"Invoice: {invoice_number}\n"
                f"Vendor: {vendor}\n"
                f"Content:\n"
                f"{document.get('text', '').strip()}"
            )
        )

    return "\n\n".join(sections)


def augment(
    documents: list[dict[str, Any]],
    threshold: float | None = None,
) -> dict[str, Any]:
    """
    Prepare retrieved documents for RAG generation.

    Pipeline:

        retrieve
           ↓
        score filtering
           ↓
        deduplication
           ↓
        ranking
           ↓
        context assembly
    """

    threshold = (
        threshold
        if threshold is not None
        else 0.0
    )

    filtered = _filter_by_score(
        documents,
        threshold,
    )

    unique = _deduplicate(filtered)

    ranked = _rank_documents(unique)

    context = _build_context(ranked)

    return {
        "documents": ranked,
        "context": context,
        "document_count": len(ranked),
        "has_sufficient_context": bool(ranked),
    }


def augment_state(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Augment the documents stored in workflow state.
    """

    documents = list(
        state.get("rag_documents") or []
    )

    threshold = float(
        state.get(
            "rag_score_threshold",
            0.0,
        )
    )

    # If the state doesn't explicitly carry the
    # threshold, use the application configuration.
    if threshold == 0.0:
        from agent.config import settings

        threshold = settings.rag_score_threshold

    result = augment(
        documents=documents,
        threshold=threshold,
    )

    return {
        "rag_documents": result["documents"],
        "rag_context": result["context"],
        "rag_context_sufficient": result[
            "has_sufficient_context"
        ],
    }