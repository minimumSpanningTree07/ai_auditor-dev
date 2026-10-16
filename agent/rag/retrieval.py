from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient

from agent.config import settings


def _client() -> QdrantClient:
    return QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )


def _embed(text: str) -> list[float]:
    from litellm import embedding

    response = embedding(
        model=settings.embedding_model,
        input=[text],
    )

    return response.data[0]["embedding"]


def retrieve_documents(
    question: str,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    if not question.strip():
        return []

    client = _client()

    try:
        vector = _embed(question)

        results = client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            limit=top_k or settings.rag_top_k,
            with_payload=True,
        ).points

    except Exception:
        return []

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
                "text": payload.get("text", ""),
            }
        )

    return documents