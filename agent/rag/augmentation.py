from __future__ import annotations

from typing import Any


def augment_context(
    question: str,
    documents: list[dict[str, Any]],
) -> str:
    if not documents:
        return (
            "No relevant documents were retrieved. "
            "Do not invent information."
        )

    sections: list[str] = []

    for index, document in enumerate(documents, start=1):
        text = str(document.get("text") or "").strip()

        if not text:
            continue

        sections.append(
            f"""
DOCUMENT {index}
Invoice ID: {document.get("invoice_id")}
Invoice Number: {document.get("invoice_number")}
Vendor: {document.get("vendor_name")}
PO Number: {document.get("po_number")}
Validation Status: {document.get("validation_status")}
Recommendation: {document.get("recommendation")}
Similarity Score: {document.get("score")}

CONTENT:
{text}
""".strip()
        )

    if not sections:
        return (
            "No usable document content was retrieved. "
            "Do not invent information."
        )

    return (
        f"QUESTION:\n{question.strip()}\n\n"
        "RETRIEVED CONTEXT:\n\n"
        + "\n\n---\n\n".join(sections)
    )


def build_augmented_state(
    state: dict[str, Any],
) -> dict[str, Any]:
    question = str(state.get("question") or "").strip()
    documents = state.get("retrieved_documents") or []

    return {
        "augmented_context": augment_context(
            question,
            documents,
        )
    }