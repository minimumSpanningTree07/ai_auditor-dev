from __future__ import annotations

from typing import Any

from litellm import embedding
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from agent.config import settings


def _client() -> QdrantClient:
    return QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )


def _embed_query(question: str) -> list[float]:
    response = embedding(
        model=settings.embedding_model,
        input=[question],
    )

    return response.data[0]["embedding"]


def _build_filter(
    invoice_id: str | None = None,
) -> Filter | None:
    if not invoice_id:
        return None

    return Filter(
        must=[
            FieldCondition(
                key="invoice_id",
                match=MatchValue(value=str(invoice_id)),
            )
        ]
    )


def retrieve(
    question: str,
    invoice_id: str | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve the most relevant invoice chunks from Qdrant.

    Results are returned as plain dictionaries so the rest of the
    RAG pipeline does not depend on Qdrant-specific objects.
    """

    question = question.strip()

    if not question:
        return []

    client = _client()

    limit = top_k or settings.rag_top_k

    query_vector = _embed_query(question)

    query_filter = _build_filter(invoice_id)

    response = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )

    results = response.points

    documents: list[dict[str, Any]] = []

    for result in results:
        payload = result.payload or {}

        documents.append(
            {
                "id": str(result.id),
                "score": float(result.score),
                "invoice_id": payload.get("invoice_id"),
                "file_name": payload.get("file_name"),
                "invoice_number": payload.get("invoice_number"),
                "vendor_name": payload.get("vendor_name"),
                "po_number": payload.get("po_number"),
                "validation_status": payload.get(
                    "validation_status"
                ),
                "recommendation": payload.get(
                    "recommendation"
                ),
                "chunk_index": payload.get(
                    "chunk_index"
                ),
                "total_chunks": payload.get(
                    "total_chunks"
                ),
                "text": payload.get("text", ""),
            }
        )

    return documents


def retrieve_for_state(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Retrieve documents using the question and optional invoice filter
    already present in the workflow state.
    """

    question = str(
        state.get("rag_question")
        or ""
    ).strip()

    if not question:
        return {
            "rag_documents": [],
            "rag_context": "",
        }

    invoice_id = state.get("rag_invoice_id")

    if not invoice_id:
        invoice_id = state.get("invoice_id")

    try:
        documents = retrieve(
            question=question,
            invoice_id=(
                str(invoice_id)
                if invoice_id
                else None
            ),
            top_k=settings.rag_top_k,
        )

        context_parts: list[str] = []

        for index, document in enumerate(
            documents,
            start=1,
        ):
            context_parts.append(
                (
                    f"[Document {index} | "
                    f"score={document['score']:.4f}]\n"
                    f"{document['text']}"
                )
            )

        return {
            "rag_documents": documents,
            "rag_context": "\n\n".join(
                context_parts
            ),
        }

    except Exception as exc:
        return {
            "rag_documents": [],
            "rag_context": "",
            "warnings": [
                *list(state.get("warnings") or []),
                f"RAG retrieval failed: {exc}",
            ],
        }