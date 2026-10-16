from __future__ import annotations

import hashlib
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

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


def _document_text(state: dict[str, Any]) -> str:
    lines = state.get("effective_line_items") or state.get("line_items") or []

    line_text = "\n".join(
        (
            f"SKU: {line.get('sku')}; "
            f"Description: {line.get('description')}; "
            f"Quantity: {line.get('quantity')}; "
            f"Unit Price: {line.get('unit_price')}; "
            f"Line Total: {line.get('line_total')}"
        )
        for line in lines
    )

    return f"""
Invoice Number: {state.get('effective_invoice_number') or state.get('extracted_invoice_number')}
Vendor: {state.get('effective_vendor_name') or state.get('extracted_vendor_name')}
PO Number: {state.get('effective_po_number') or state.get('extracted_po_number')}
Invoice Date: {state.get('effective_invoice_date') or state.get('extracted_invoice_date')}
Currency: {state.get('effective_currency') or state.get('extracted_currency')}
Subtotal: {state.get('effective_subtotal_amount') or state.get('extracted_subtotal_amount')}
Tax: {state.get('effective_tax_amount') or state.get('extracted_tax_amount')}
Tax Rate: {state.get('effective_tax_rate') or state.get('extracted_tax_rate')}
Total: {state.get('effective_total_amount') or state.get('extracted_total_amount')}

Validation Status: {state.get('validation_status')}
Recommendation: {state.get('recommendation')}

Discrepancies:
{state.get('discrepancies') or []}

Line Items:
{line_text}
""".strip()


def _ensure_collection(client: QdrantClient) -> None:
    collections = {
        collection.name
        for collection in client.get_collections().collections
    }

    if settings.qdrant_collection not in collections:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=settings.embedding_dimension,
                distance=Distance.COSINE,
            ),
        )


def index_invoice(
    state: dict[str, Any],
) -> dict[str, Any]:
    text = _document_text(state)

    if not text.strip():
        return {
            "warnings": [
                *list(state.get("warnings") or []),
                "No invoice content available for RAG indexing.",
            ]
        }

    try:
        client = _client()
        _ensure_collection(client)

        vector = _embed(text)

        invoice_id = str(
            state.get("invoice_id")
            or state.get("extracted_invoice_number")
            or state.get("file_name")
            or "unknown"
        )

        point_id = hashlib.sha256(
            invoice_id.encode("utf-8")
        ).hexdigest()[:32]

        payload = {
            "invoice_id": invoice_id,
            "file_name": state.get("file_name"),
            "invoice_number": state.get("effective_invoice_number")
            or state.get("extracted_invoice_number"),
            "vendor_name": state.get("effective_vendor_name")
            or state.get("extracted_vendor_name"),
            "po_number": state.get("effective_po_number")
            or state.get("extracted_po_number"),
            "validation_status": state.get("validation_status"),
            "recommendation": state.get("recommendation"),
            "text": text,
        }

        client.upsert(
            collection_name=settings.qdrant_collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )

        return {
            "warnings": list(state.get("warnings") or []),
            "rag_indexed": True,
        }

    except Exception as exc:
        return {
            "warnings": [
                *list(state.get("warnings") or []),
                f"RAG indexing failed: {exc}",
            ],
            "rag_indexed": False,
        }