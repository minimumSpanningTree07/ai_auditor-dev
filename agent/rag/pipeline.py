from __future__ import annotations

from typing import Any

from agent.config import settings
from agent.services.database import db
from agent.rag.retrieval import retrieve
from agent.rag.augmentation import augment
from agent.rag.generation import generate
from agent.rag.reflection import reflect


def _structured_invoice_context(invoice_id: str | None) -> str:
    """Add authoritative saved audit facts to semantic context for a selected invoice."""
    if not invoice_id:
        return ""
    invoice = db.fetch_one(
        """SELECT file_name, invoice_number, vendor_name, po_number, invoice_date,
                  currency, subtotal_amount, tax_amount, tax_rate, total_amount,
                  validation_status, recommendation, human_review_required
           FROM audit.invoices WHERE invoice_id = %s""",
        [invoice_id],
    )
    if not invoice:
        return ""
    discrepancies = db.fetch_all(
        """SELECT discrepancy_type, severity, message, details, status
           FROM audit.discrepancies WHERE invoice_id = %s ORDER BY id""",
        [invoice_id],
    )
    lines = db.fetch_all(
        """SELECT line_number, sku, description, quantity, unit_price, line_total, source
           FROM audit.invoice_line_items WHERE invoice_id = %s ORDER BY line_number""",
        [invoice_id],
    )
    fields = [
        "AUTHORITATIVE SAVED AUDIT RECORD (use for current status and structured values)",
        f"File: {invoice.get('file_name') or 'unknown'}",
        f"Invoice number: {invoice.get('invoice_number') or 'not extracted'}",
        f"Vendor: {invoice.get('vendor_name') or 'not identified'}",
        f"Purchase order: {invoice.get('po_number') or 'not identified'}",
        f"Invoice date: {invoice.get('invoice_date') or 'not recorded'}",
        f"Currency: {invoice.get('currency') or 'not validated'}",
        f"Subtotal: {invoice.get('subtotal_amount') if invoice.get('subtotal_amount') is not None else 'not recorded'}",
        f"Tax: {invoice.get('tax_amount') if invoice.get('tax_amount') is not None else 'not recorded'}",
        f"Tax rate: {invoice.get('tax_rate') if invoice.get('tax_rate') is not None else 'not recorded'}",
        f"Total: {invoice.get('total_amount') if invoice.get('total_amount') is not None else 'not recorded'}",
        f"Validation status: {invoice.get('validation_status') or 'unknown'}",
        f"Recommendation: {invoice.get('recommendation') or 'not recorded'}",
        f"Human review required: {bool(invoice.get('human_review_required'))}",
        "Line items:",
    ]
    if lines:
        for line in lines:
            fields.append(
                f"- Line {line.get('line_number')}: SKU {line.get('sku') or 'unknown'}; "
                f"description {line.get('description') or 'not recorded'}; "
                f"quantity {line.get('quantity')}; unit price {line.get('unit_price')}; "
                f"line total {line.get('line_total')}"
            )
    else:
        fields.append("- No line items are stored.")
    fields.append("Recorded discrepancies:")
    if discrepancies:
        for item in discrepancies:
            fields.append(
                f"- [{item.get('severity') or 'unspecified'}] "
                f"{item.get('discrepancy_type') or 'validation issue'}: "
                f"{item.get('message') or item.get('details') or 'No explanation recorded.'}; "
                f"status={item.get('status') or 'unknown'}"
            )
    else:
        fields.append("- No discrepancies are recorded.")
    return "\n".join(fields)


def run_rag(question: str, invoice_id: str | None = None) -> dict[str, Any]:
    max_retries = int(settings.rag_max_retries)
    structured_context = _structured_invoice_context(invoice_id)
    last_result: dict[str, Any] = {
        "question": question, "invoice_id": invoice_id, "documents": [],
        "context": structured_context, "answer": "", "reflection": {},
        "accepted": False, "retry_count": 0,
        "structured_context_used": bool(structured_context),
    }

    for attempt in range(max_retries + 1):
        documents = retrieve(question=question, invoice_id=invoice_id)
        augmented = augment(documents)
        semantic_context = str(augmented.get("context") or "").strip()
        context_parts = [part for part in (semantic_context, structured_context) if part]
        context = "\n\n--- VERIFIED AUDIT DATA ---\n\n".join(context_parts)

        # A selected invoice's saved audit record is valid evidence even when
        # semantic retrieval scores are weak or the Qdrant index is empty.
        if not context.strip():
            last_result = {
                **last_result, "documents": documents, "context": "", "answer": "",
                "reflection": {"overall_score": 0.0, "accepted": False,
                               "reason": "No relevant invoice evidence was retrieved and no saved audit facts were available."},
                "accepted": False, "retry_count": attempt,
            }
            if attempt < max_retries:
                continue
            break

        try:
            answer = str(generate(question=question, context=context) or "").strip()
        except Exception as exc:
            last_result = {
                **last_result, "documents": documents, "context": context,
                "answer": "", "reflection": {"overall_score": 0.0, "accepted": False,
                "reason": f"Answer generation failed: {exc}"},
                "accepted": False, "retry_count": attempt,
                "structured_context_used": bool(structured_context),
            }
            # A provider/API exception will not be fixed by repeating the same
            # request with the same model and context. Return to the API layer,
            # which can use the deterministic saved-audit answer instead.
            break
        if not answer:
            last_result = {
                **last_result, "documents": documents, "context": context,
                "answer": "", "reflection": {"overall_score": 0.0, "accepted": False,
                "reason": "The answer model returned an empty response."},
                "accepted": False, "retry_count": attempt,
                "structured_context_used": bool(structured_context),
            }
            break

        try:
            reflection = reflect(question=question, context=context, answer=answer)
        except Exception as exc:
            reflection = {
                "context_relevance": 0.0, "groundedness": 0.0,
                "question_relevance": 0.0, "overall_score": 0.0,
                "reason": f"Answer generated, but the quality evaluator failed: {exc}",
                "accepted": False, "reflection_failed": True,
            }
        accepted = bool(reflection.get("accepted", False))
        last_result = {
            "question": question, "invoice_id": invoice_id,
            "documents": documents, "context": context, "answer": answer,
            "reflection": reflection, "accepted": accepted,
            "retry_count": attempt,
            "structured_context_used": bool(structured_context),
        }
        if accepted or reflection.get("reflection_failed"):
            # Don't spend repeated model calls trying to recover from an
            # evaluator outage; preserve the generated answer and its status.
            break
    return last_result
