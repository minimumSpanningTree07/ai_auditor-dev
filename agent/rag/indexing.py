from __future__ import annotations

import hashlib
import uuid
from typing import Any

from litellm import embedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from agent.config import settings


def _client() -> QdrantClient:
    return QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )


def _embed(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings through LiteLLM.

    The actual provider/model is controlled by:
        settings.embedding_model
    """

    response = embedding(
        model=settings.embedding_model,
        input=texts,
    )

    return [
        item["embedding"]
        for item in response.data
    ]


def _effective_value(
    state: dict[str, Any],
    effective_key: str,
    original_key: str,
    plain_key: str | None = None,
) -> Any:
    value = state.get(effective_key)

    if value is not None and value != "":
        return value

    value = state.get(original_key)

    if value is not None and value != "":
        return value

    if plain_key:
        value = state.get(plain_key)

        if value is not None and value != "":
            return value

    return None


def _line_items_text(state: dict[str, Any]) -> str:
    lines = (
        state.get("effective_line_items")
        or state.get("line_items")
        or []
    )

    if not lines:
        return "No line items available."

    result: list[str] = []

    for index, line in enumerate(lines, start=1):
        result.append(
            (
                f"Line {index}: "
                f"SKU={line.get('sku')}; "
                f"Description={line.get('description')}; "
                f"Quantity={line.get('quantity')}; "
                f"Unit Price={line.get('unit_price')}; "
                f"Line Total={line.get('line_total')}"
            )
        )

    return "\n".join(result)


def _invoice_summary(state: dict[str, Any]) -> str:
    return f"""
Invoice Number:
{_effective_value(
    state,
    "effective_invoice_number",
    "extracted_invoice_number",
    "invoice_number",
)}

Vendor:
{_effective_value(
    state,
    "effective_vendor_name",
    "extracted_vendor_name",
    "vendor_name",
)}

PO Number:
{_effective_value(
    state,
    "effective_po_number",
    "extracted_po_number",
    "po_number",
)}

Invoice Date:
{_effective_value(
    state,
    "effective_invoice_date",
    "extracted_invoice_date",
    "invoice_date",
)}

Currency:
{_effective_value(
    state,
    "effective_currency",
    "extracted_currency",
    "currency",
)}

Subtotal:
{_effective_value(
    state,
    "effective_subtotal_amount",
    "extracted_subtotal_amount",
    "subtotal_amount",
)}

Tax:
{_effective_value(
    state,
    "effective_tax_amount",
    "extracted_tax_amount",
    "tax_amount",
)}

Tax Rate:
{_effective_value(
    state,
    "effective_tax_rate",
    "extracted_tax_rate",
    "tax_rate",
)}

Total:
{_effective_value(
    state,
    "effective_total_amount",
    "extracted_total_amount",
    "total_amount",
)}

Validation Status:
{state.get("validation_status")}

Recommendation:
{state.get("recommendation")}
""".strip()


def _discrepancies_text(state: dict[str, Any]) -> str:
    discrepancies = state.get("discrepancies") or []

    if not discrepancies:
        return "No discrepancies detected."

    lines: list[str] = []

    for index, discrepancy in enumerate(discrepancies, start=1):
        if isinstance(discrepancy, dict):
            lines.append(
                (
                    f"Discrepancy {index}: "
                    f"field={discrepancy.get('field')}; "
                    f"invoice_value={discrepancy.get('invoice_value')}; "
                    f"erp_value={discrepancy.get('erp_value')}; "
                    f"deviation={discrepancy.get('deviation')}; "
                    f"message={discrepancy.get('message')}"
                )
            )
        else:
            lines.append(
                f"Discrepancy {index}: {discrepancy}"
            )

    return "\n".join(lines)


def _raw_invoice_text(state: dict[str, Any]) -> str:
    """
    Preserve the original extracted invoice text.

    This is important because the RAG index must not contain
    only normalized/effective values.
    """

    return str(
        state.get("raw_extracted_text")
        or state.get("extracted_text")
        or ""
    ).strip()


def _report_text(state: dict[str, Any]) -> str:
    report = state.get("report")

    if isinstance(report, str):
        return report.strip()

    if isinstance(report, dict):
        parts: list[str] = []

        for key, value in report.items():
            parts.append(f"{key}: {value}")

        return "\n".join(parts)

    return ""


def _build_document(state: dict[str, Any]) -> str:
    """
    Build the complete searchable invoice document.

    The document intentionally contains:
    - normalized invoice fields
    - line items
    - discrepancies
    - original extracted text
    - generated report

    This allows open-ended RAG questions to use both
    structured and unstructured invoice information.
    """

    sections: list[str] = []

    summary = _invoice_summary(state)
    if summary:
        sections.append(
            "=== INVOICE SUMMARY ===\n"
            + summary
        )

    line_items = _line_items_text(state)
    if line_items:
        sections.append(
            "=== LINE ITEMS ===\n"
            + line_items
        )

    discrepancies = _discrepancies_text(state)
    if discrepancies:
        sections.append(
            "=== DISCREPANCIES ===\n"
            + discrepancies
        )

    raw_text = _raw_invoice_text(state)
    if raw_text:
        sections.append(
            "=== ORIGINAL INVOICE TEXT ===\n"
            + raw_text
        )

    report_text = _report_text(state)
    if report_text:
        sections.append(
            "=== AUDIT REPORT ===\n"
            + report_text
        )

    return "\n\n".join(sections).strip()


def _chunk_text(
    text: str,
    max_chars: int = 1800,
    overlap: int = 250,
) -> list[str]:
    """
    Split invoice/report content into overlapping chunks.

    Character-based chunking is intentionally simple and deterministic
    for this capstone. Overlap prevents important information from being
    lost at chunk boundaries.
    """

    text = text.strip()

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []

    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(
            start + max_chars,
            text_length,
        )

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = end - overlap

        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def _ensure_collection(client: QdrantClient) -> None:
    collections = {
        collection.name
        for collection in client.get_collections().collections
    }

    if settings.qdrant_collection in collections:
        return

    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(
            size=settings.embedding_dimension,
            distance=Distance.COSINE,
        ),
    )


def _invoice_filter(invoice_id: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(
                key="invoice_id",
                match=MatchValue(value=invoice_id),
            )
        ]
    )


def _delete_existing_invoice(
    client: QdrantClient,
    invoice_id: str,
) -> None:
    """
    Remove previous chunks for this invoice.

    Re-indexing therefore replaces the derived Qdrant representation
    instead of accumulating stale vectors.
    """

    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=_invoice_filter(invoice_id),
    )


def _stable_point_id(
    invoice_id: str,
    chunk_index: int,
) -> str:
    """
    Generate a deterministic UUID for each invoice chunk.
    """

    value = f"{invoice_id}:chunk:{chunk_index}"

    digest = hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()

    return str(
        uuid.UUID(digest[:32])
    )

def _payload(
    state: dict[str, Any],
    invoice_id: str,
    chunk: str,
    chunk_index: int,
    total_chunks: int,
) -> dict[str, Any]:

    return {
        "invoice_id": invoice_id,
        "file_name": state.get("file_name"),

        "invoice_number": _effective_value(
            state,
            "effective_invoice_number",
            "extracted_invoice_number",
            "invoice_number",
        ),

        "vendor_name": _effective_value(
            state,
            "effective_vendor_name",
            "extracted_vendor_name",
            "vendor_name",
        ),

        "po_number": _effective_value(
            state,
            "effective_po_number",
            "extracted_po_number",
            "po_number",
        ),

        "validation_status": state.get(
            "validation_status"
        ),

        "recommendation": state.get(
            "recommendation"
        ),

        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "text": chunk,
    }

   


def index_invoice(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Index the completed invoice audit into Qdrant.

    Called after persistence/report generation.

    Returns state updates rather than mutating the state directly.
    """

    document = _build_document(state)

    if not document:
        return {
            "warnings": [
                *list(state.get("warnings") or []),
                "No invoice content available for RAG indexing.",
            ],
            "rag_indexed": False,
        }

    invoice_id = str(
        state.get("invoice_id")
        or state.get("extracted_invoice_number")
        or state.get("file_name")
        or "unknown"
    )

    try:
        client = _client()

        _ensure_collection(client)

        chunks = _chunk_text(document)

        if not chunks:
            return {
                "warnings": [
                    *list(state.get("warnings") or []),
                    "Invoice produced no RAG chunks.",
                ],
                "rag_indexed": False,
            }

        vectors = _embed(chunks)

        if len(vectors) != len(chunks):
            raise RuntimeError(
                "Embedding count does not match chunk count."
            )

        # Replace any previous representation of this invoice.
        _delete_existing_invoice(
            client,
            invoice_id,
        )

        total_chunks = len(chunks)

        points: list[PointStruct] = []

        for index, (chunk, vector) in enumerate(
            zip(chunks, vectors)
        ):
            points.append(
                PointStruct(
                    id=_stable_point_id(
                        invoice_id,
                        index,
                    ),
                    vector=vector,
                    payload=_payload(
                        state,
                        invoice_id,
                        chunk,
                        index,
                        total_chunks,
                    ),
                )
            )

        client.upsert(
            collection_name=settings.qdrant_collection,
            points=points,
        )

        return {
            "warnings": list(
                state.get("warnings") or []
            ),
            "rag_indexed": True,
            "rag_chunk_count": total_chunks,
        }

    except Exception as exc:
        return {
            "warnings": [
                *list(state.get("warnings") or []),
                f"RAG indexing failed: {exc}",
            ],
            "rag_indexed": False,
        }