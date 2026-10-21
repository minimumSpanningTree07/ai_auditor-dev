from __future__ import annotations

from typing import Any

from agent.config import settings
from agent.services.database import db
from agent.rag.retrieval import retrieve
from agent.rag.augmentation import augment
from agent.rag.generation import generate
from agent.rag.reflection import reflect
from agent.rag.ragas_metrics import evaluate_answer


def _authoritative_context(invoice_id: str | None) -> str:
    """Build current truth from PostgreSQL. Qdrant is supporting evidence only."""
    if invoice_id:
        invoice = db.fetch_one(
            """SELECT invoice_id, file_name, invoice_number, vendor_name, po_number,
                      invoice_date, currency, subtotal_amount, tax_amount, tax_rate,
                      total_amount, validation_status, recommendation,
                      human_review_required, updated_at
               FROM audit.invoices WHERE invoice_id = %s""",
            [invoice_id],
        )
        if not invoice:
            return ""
        rows = db.fetch_all(
            """SELECT line_number, sku, description, quantity, unit_price, line_total, source
               FROM audit.invoice_line_items WHERE invoice_id = %s ORDER BY line_number""",
            [invoice_id],
        )
        discrepancies = db.fetch_all(
            """SELECT discrepancy_type, severity, message, details, status
               FROM audit.discrepancies WHERE invoice_id = %s AND UPPER(status) = 'OPEN' ORDER BY id""",
            [invoice_id],
        )
        feedback = db.fetch_all(
            """SELECT decision, feedback, corrections, created_at
               FROM audit.human_feedback WHERE invoice_id = %s ORDER BY created_at DESC""",
            [invoice_id],
        )
        parts = ["=== AUTHORITATIVE CURRENT AUDIT TABLE ==="]
        for key, value in invoice.items():
            if key != "invoice_id":
                parts.append(f"{key}: {value}")
        parts.append("line_items:")
        for row in rows:
            parts.append(f"- {row}")
        parts.append("CURRENT OPEN DISCREPANCIES:")
        for row in discrepancies:
            parts.append(f"- {row}")
        if not discrepancies:
            parts.append("- none")
        parts.append(f"open_discrepancy_count: {len(discrepancies)}")
        parts.append("human_feedback_history:")
        for row in feedback:
            parts.append(f"- {row}")
        return "\n".join(parts)

    invoices = db.fetch_all(
        """SELECT invoice_id, file_name, invoice_number, vendor_name, po_number,
                  invoice_date, currency, total_amount, validation_status,
                  recommendation, human_review_required, updated_at
           FROM audit.invoices ORDER BY updated_at DESC LIMIT 100"""
    )
    if not invoices:
        return ""
    return "=== AUTHORITATIVE CURRENT AUDIT TABLE (ALL INVOICES) ===\n" + "\n".join(str(r) for r in invoices)


def run_rag(question: str, invoice_id: str | None = None) -> dict[str, Any]:
    max_retries = int(settings.rag_max_retries)
    authoritative = _authoritative_context(invoice_id)
    last: dict[str, Any] = {
        "question": question, "invoice_id": invoice_id, "documents": [],
        "context": authoritative, "answer": "", "reflection": {},
        "accepted": False, "retry_count": 0,
        "structured_context_used": bool(authoritative),
        "ragas": {},
    }

    for attempt in range(max_retries + 1):
        try:
            documents = retrieve(question=question, invoice_id=invoice_id)
        except Exception:
            documents = []
        augmented = augment(documents)
        semantic_context = str(augmented.get("context") or "").strip()
        context = "\n\n".join(p for p in (authoritative, semantic_context) if p)
        if not context:
            last["retry_count"] = attempt
            if attempt < max_retries:
                continue
            break
        try:
            answer = str(generate(question=question, context=context) or "").strip()
        except Exception as exc:
            last.update({"documents": documents, "context": context, "retry_count": attempt,
                         "reflection": {"overall_score": 0.0, "accepted": False, "reason": str(exc)}})
            break
        if not answer:
            break
        try:
            reflection = reflect(question=question, context=context, answer=answer)
        except Exception as exc:
            reflection = {"context_relevance": 0.0, "groundedness": 0.0,
                          "question_relevance": 0.0, "overall_score": 0.0,
                          "accepted": False, "reflection_failed": True,
                          "reason": f"Reflection failed: {exc}"}
        try:
            ragas = evaluate_answer(question=question, answer=answer,
                                    contexts=[authoritative] + ([semantic_context] if semantic_context else []),
                                    reference=None)
        except Exception as exc:
            ragas = {"available": False, "error": str(exc),
                     "faithfulness": reflection.get("groundedness", 0.0),
                     "answer_relevancy": reflection.get("question_relevance", 0.0),
                     "context_relevance": reflection.get("context_relevance", 0.0),
                     "factual_accuracy": reflection.get("groundedness", 0.0),
                     "overall": reflection.get("overall_score", 0.0),
                     "source": "reflection_fallback"}
        last = {"question": question, "invoice_id": invoice_id, "documents": documents,
                "context": context, "answer": answer, "reflection": reflection,
                "accepted": bool(reflection.get("accepted")), "retry_count": attempt,
                "structured_context_used": bool(authoritative), "ragas": ragas}
        if last["accepted"] or reflection.get("reflection_failed"):
            break
    return last
