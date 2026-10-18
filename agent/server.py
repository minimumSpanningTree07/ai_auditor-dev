from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from agent.watcher import InvoiceWatcher
from agent.config import settings
from agent.graph import process_invoice
from agent.services.database import db
from agent.services.erp_client import erp_client
from agent.services.cache import cache
from agent.services.checksum import calculate_sha256
logging.basicConfig(
    level=getattr(
        logging,
        str(settings.log_level).upper(),
        logging.INFO,
    ),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
)

INCOMING_DIR = Path("/app/data/incoming")

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
}

MAX_UPLOAD_BYTES = 25 * 1024 * 1024

watcher = InvoiceWatcher(directory=INCOMING_DIR)
watcher_task: asyncio.Task | None = None


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------

class RevalidationRequest(BaseModel):
    corrections: dict[str, Any] = Field(default_factory=dict)
    decision: str | None = None
    feedback: str | None = None


class HumanFeedbackRequest(BaseModel):
    feedback: str = Field(..., min_length=1, max_length=10000)


class ResetWorkspaceRequest(BaseModel):
    confirmation: str = Field(..., min_length=1)


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    invoice_id: str | None = None


class QueryResponse(BaseModel):
    question: str
    invoice_id: str | None
    answer: str
    documents: list[dict[str, Any]] = Field(default_factory=list)
    reflection: dict[str, Any] = Field(default_factory=dict)
    accepted: bool = False
    retry_count: int = 0
    fallback: bool = False
    answer_source: str = "rag"
    answer_needs_verification: bool = False
# ------------------------------------------------------------------
# Startup / shutdown
# ------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    global watcher_task

    INCOMING_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    watcher_task = asyncio.create_task(
        watcher.run()
    )


@app.on_event("shutdown")
async def shutdown_event():
    global watcher_task

    if watcher_task is not None:
        watcher_task.cancel()

        try:
            await watcher_task
        except asyncio.CancelledError:
            pass
        finally:
            watcher_task = None


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "database": db.health_check(),
        "erp": erp_client.health_check(),
        "redis": cache.health_check(),
    }


# ------------------------------------------------------------------
# Invoice APIs
# ------------------------------------------------------------------

@app.delete("/api/uploads/queue")
def clear_pending_upload_queue() -> dict[str, Any]:
    """Remove only unprocessed incoming files; saved audit records are preserved."""
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    processed_rows = db.fetch_all(
        "SELECT file_path, file_checksum FROM audit.invoices"
    )
    known_paths = {str(Path(row["file_path"]).resolve()) for row in processed_rows if row.get("file_path")}
    known_checksums = {str(row["file_checksum"]).lower() for row in processed_rows if row.get("file_checksum")}
    removed: list[str] = []
    skipped: list[str] = []
    for path in INCOMING_DIR.iterdir():
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        key = str(path.resolve())
        if key in watcher.processing:
            skipped.append(path.name)
            continue
        try:
            checksum = calculate_sha256(path).lower()
        except OSError:
            skipped.append(path.name)
            continue
        if key in known_paths or checksum in known_checksums:
            skipped.append(path.name)
            continue
        try:
            path.unlink()
            removed.append(path.name)
            watcher.completed.pop(key, None)
            watcher.retry_after.pop(key, None)
        except OSError:
            skipped.append(path.name)
    return {"removed_count": len(removed), "removed_files": removed,
            "skipped_count": len(skipped), "skipped_files": skipped,
            "message": "Removed pending files only. Saved invoices and their source files were preserved."}


@app.post("/api/admin/reset-invoice-workspace")
def reset_invoice_workspace(request: ResetWorkspaceRequest) -> dict[str, Any]:
    """Destructively clear invoice audit data and local source files for a fresh import."""
    if request.confirmation != "RESET-INVOICES":
        raise HTTPException(status_code=400, detail="Type RESET-INVOICES to confirm this destructive action.")
    if watcher.processing:
        raise HTTPException(status_code=409, detail="Invoice processing is currently active. Wait for it to finish, then retry the reset.")

    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    removed_files = 0
    for path in INCOMING_DIR.iterdir():
        if path.is_file():
            try:
                path.unlink()
                removed_files += 1
            except OSError as exc:
                raise HTTPException(status_code=500, detail=f"Could not remove incoming file {path.name}: {exc}") from exc

    # Invoice-owned audit tables cascade from audit.invoices. ERP seed tables and
    # the PostgreSQL volume are intentionally untouched.
    try:
        deleted_records = db.execute("DELETE FROM audit.invoices")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not clear audit records: {exc}") from exc

    vector_collection_cleared = False
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        if client.collection_exists(settings.qdrant_collection):
            client.delete_collection(settings.qdrant_collection)
        vector_collection_cleared = True
        client.close()
    except Exception as exc:
        logger.exception("Could not clear Qdrant invoice collection during workspace reset")
        raise HTTPException(status_code=500, detail=f"Audit records were cleared, but the Qdrant collection could not be cleared: {exc}") from exc

    reports_dir = Path("/app/outputs/reports")
    removed_reports = 0
    if reports_dir.exists():
        for path in reports_dir.iterdir():
            if path.is_file():
                try:
                    path.unlink()
                    removed_reports += 1
                except OSError:
                    logger.warning("Could not remove report file %s", path)

    watcher.completed.clear()
    watcher.retry_after.clear()
    watcher.known_files.clear()
    return {"message": "Invoice workspace reset. You can upload a fresh set of invoices.",
            "removed_source_files": removed_files, "deleted_invoice_records": deleted_records,
            "removed_report_files": removed_reports, "vector_collection_cleared": vector_collection_cleared}


@app.get("/api/uploads/status")
def upload_status() -> dict[str, Any]:
    """Return a combined view of files in the incoming folder and processed invoices."""
    processed_rows = db.fetch_all(
        """
        SELECT invoice_id, file_name, file_path, file_checksum, invoice_number, vendor_name,
               validation_status, recommendation, updated_at
        FROM audit.invoices
        ORDER BY updated_at DESC
        """
    )
    processed_by_path = {}
    processed_by_checksum = {}
    for row in processed_rows:
        file_path = row.get("file_path")
        if file_path:
            processed_by_path[str(Path(file_path).resolve())] = row
        checksum = row.get("file_checksum")
        if checksum:
            processed_by_checksum[str(checksum).lower()] = row

    files: list[dict[str, Any]] = []
    present_paths: set[str] = set()
    present_invoice_ids: set[str] = set()
    for path in sorted(INCOMING_DIR.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        resolved = str(path.resolve())
        present_paths.add(resolved)
        record = processed_by_path.get(resolved)
        if record is None:
            try:
                record = processed_by_checksum.get(calculate_sha256(path).lower())
            except OSError:
                record = None
        if record and record.get("invoice_id"):
            present_invoice_ids.add(str(record["invoice_id"]))
        key = resolved
        if key in watcher.processing:
            status = "processing"
        elif record:
            status = str(record.get("validation_status") or "processed")
        elif key in watcher.retry_after:
            status = "retry scheduled"
        else:
            status = "uploaded / queued"

        stored_name = path.name
        display_name = re.sub(r"^[0-9a-f]{32}__", "", stored_name, flags=re.IGNORECASE)
        files.append({
            "file_name": display_name,
            "stored_filename": stored_name,
            "status": status,
            "invoice_id": record.get("invoice_id") if record else None,
            "invoice_number": record.get("invoice_number") if record else None,
            "vendor_name": record.get("vendor_name") if record else None,
            "recommendation": record.get("recommendation") if record else None,
            "updated_at": record.get("updated_at") if record else None,
        })

    # Keep processed records visible even if their source file has since been removed.
    for row in processed_rows:
        file_path = row.get("file_path")
        if row.get("invoice_id") and str(row["invoice_id"]) in present_invoice_ids:
            continue
        if file_path and str(Path(file_path).resolve()) in present_paths:
            continue
        files.append({
            "file_name": row.get("file_name") or "Unknown file",
            "stored_filename": None,
            "status": str(row.get("validation_status") or "processed") + " (source file missing)",
            "invoice_id": row.get("invoice_id"),
            "invoice_number": row.get("invoice_number"),
            "vendor_name": row.get("vendor_name"),
            "recommendation": row.get("recommendation"),
            "updated_at": row.get("updated_at"),
        })

    return {"files": files, "count": len(files), "incoming_directory": str(INCOMING_DIR)}


@app.get("/api/invoices")
def list_invoices() -> list[dict[str, Any]]:
    return db.fetch_all(
        """
        SELECT
            invoice_id,
            file_name,
            invoice_number,
            vendor_name,
            po_number,
            invoice_date,
            currency,
            subtotal_amount,
            tax_amount,
            total_amount,
            validation_status,
            recommendation,
            human_review_required,
            report_path,
            updated_at
        FROM audit.invoices
        ORDER BY updated_at DESC
        """
    )


@app.get("/api/invoices/{invoice_id}")
def get_invoice(
    invoice_id: str,
) -> dict[str, Any]:

    invoice = db.fetch_one(
        """
        SELECT *
        FROM audit.invoices
        WHERE invoice_id = %s
        """,
        [invoice_id],
    )

    if not invoice:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    source_path = Path(invoice.get("file_path") or "")
    source_available = source_path.is_file()
    if not source_available and invoice.get("file_checksum"):
        for candidate in INCOMING_DIR.glob("*"):
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    if calculate_sha256(candidate).lower() == str(invoice["file_checksum"]).lower():
                        source_available = True
                        break
                except OSError:
                    continue
    invoice["source_available"] = source_available

    invoice["line_items"] = db.fetch_all(
        """
        SELECT *
        FROM audit.invoice_line_items
        WHERE invoice_id = %s
        ORDER BY line_number
        """,
        [invoice_id],
    )

    invoice["discrepancies"] = db.fetch_all(
        """
        SELECT *
        FROM audit.discrepancies
        WHERE invoice_id = %s
        ORDER BY id
        """,
        [invoice_id],
    )

    invoice["feedback"] = db.fetch_all(
        """
        SELECT *
        FROM audit.human_feedback
        WHERE invoice_id = %s
        ORDER BY created_at DESC
        """,
        [invoice_id],
    )

    return invoice


# ------------------------------------------------------------------
# Upload
# ------------------------------------------------------------------

@app.post(
    "/api/invoices/upload",
    status_code=202,
)
async def upload_invoice(
    file: UploadFile = File(...),
):
    """Save an invoice for asynchronous processing."""

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided.",
        )

    extension = Path(
        file.filename
    ).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type: "
                f"{extension or 'unknown'}"
            ),
        )

    destination: Path | None = None

    try:
        INCOMING_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        original_name = Path(file.filename.replace("\\", "/")).name
        original_stem = Path(original_name).stem
        safe_stem = re.sub(r"[^A-Za-z0-9._ -]", "_", original_stem).strip(" ._") or "invoice"
        safe_name = f"{uuid.uuid4().hex}__{safe_stem}{extension}"

        destination = (
            INCOMING_DIR / safe_name
        )

        size = 0

        with destination.open("wb") as output:
            while True:
                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                size += len(chunk)

                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "File exceeds the "
                            "25 MB upload limit."
                        ),
                    )

                output.write(chunk)

        if size == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )

        checksum = calculate_sha256(destination)
        existing = db.fetch_one(
            """SELECT invoice_id, file_name, invoice_number, vendor_name,
                      validation_status, recommendation
               FROM audit.invoices WHERE file_checksum = %s
               ORDER BY updated_at DESC LIMIT 1""",
            [checksum],
        )
        if existing:
            # Keep a fresh copy of the original binary available for revalidation,
            # and repair stale file_path values left by old/moved project folders.
            db.execute(
                "UPDATE audit.invoices SET file_path = %s, file_size = %s, updated_at = NOW() WHERE invoice_id = %s",
                [str(destination.resolve()), size, existing["invoice_id"]],
            )
            logger.info(
                "Duplicate invoice upload linked to existing record invoice_id=%s file=%s",
                existing["invoice_id"], safe_name,
            )
            return {
                "status": "duplicate",
                "filename": file.filename,
                "stored_filename": safe_name,
                "size_bytes": size,
                "invoice_id": existing["invoice_id"],
                "invoice_number": existing.get("invoice_number"),
                "validation_status": existing.get("validation_status"),
                "recommendation": existing.get("recommendation"),
                "message": (
                    "This file matches an invoice already in the audit database. "
                    "It was linked to the existing invoice record; no duplicate audit record was created."
                ),
            }

        logger.info(
            "Invoice uploaded: original=%s stored=%s bytes=%s",
            file.filename, safe_name, size,
        )
        return {
            "status": "queued",
            "filename": file.filename,
            "stored_filename": safe_name,
            "size_bytes": size,
            "message": "Upload saved; awaiting invoice processing.",
        }

    except HTTPException:
        if destination is not None:
            destination.unlink(
                missing_ok=True
            )
        raise

    except Exception:
        if destination is not None:
            destination.unlink(
                missing_ok=True
            )

        logger.exception(
            "Invoice upload failed for %r",
            file.filename,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Upload failed. "
                "Check the API server logs."
            ),
        )

    finally:
        await file.close()

@app.get("/api/dashboard/summary")
def dashboard_summary():
    try:
        return db.get_dashboard_summary()
    except Exception as exc:
        logger.exception("Dashboard summary failed")
        raise HTTPException(
            status_code=500,
            detail=f"Dashboard summary failed: {exc}",
        )
# ------------------------------------------------------------------
# HITL / Revalidation
# ------------------------------------------------------------------

@app.post("/api/invoices/{invoice_id}/feedback")
def save_human_feedback(invoice_id: str, request: HumanFeedbackRequest) -> dict[str, Any]:
    """Save an auditor note without re-running extraction or validation."""
    invoice = db.fetch_one(
        "SELECT invoice_id, file_name FROM audit.invoices WHERE invoice_id = %s",
        [invoice_id],
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    note = request.feedback.strip()
    if not note:
        raise HTTPException(status_code=422, detail="Feedback note cannot be blank")
    db.execute(
        """INSERT INTO audit.human_feedback (invoice_id, decision, feedback, corrections)
           VALUES (%s, %s, %s, %s::jsonb)""",
        [invoice_id, "feedback_only", note, json.dumps({})],
    )
    return {"status": "saved", "invoice_id": invoice_id, "message": f"Feedback saved for {invoice.get('file_name') or invoice_id}. No revalidation was run."}


@app.post(
    "/api/invoices/{invoice_id}/revalidate"
)
def revalidate_invoice(
    invoice_id: str,
    request: RevalidationRequest,
) -> dict[str, Any]:

    invoice = db.fetch_one(
        """
        SELECT
            invoice_id,
            file_path,
            file_name,
            file_checksum
        FROM audit.invoices
        WHERE invoice_id = %s
        """,
        [invoice_id],
    )

    if not invoice:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    file_path = Path(invoice.get("file_path") or "")
    if not file_path.is_file():
        # A moved project folder or old filename may leave a stale path in PostgreSQL.
        # Recover the source by checksum before asking the user to upload it again.
        expected_checksum = invoice.get("file_checksum")
        recovered = None
        if expected_checksum:
            for candidate in INCOMING_DIR.glob("*"):
                if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                    try:
                        if calculate_sha256(candidate) == expected_checksum:
                            recovered = candidate
                            break
                    except OSError:
                        logger.warning("Unable to check candidate invoice file %s", candidate)
        if recovered:
            file_path = recovered.resolve()
            db.execute(
                "UPDATE audit.invoices SET file_path = %s WHERE invoice_id = %s",
                [str(file_path), invoice_id],
            )
        else:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The original invoice file is missing from data/incoming. "
                    "Re-upload the same file, then retry revalidation. Existing audit data was preserved."
                ),
            )

    allowed_decisions = {None, "revalidate", "corrected", "approved", "rejected", "approve", "reject"}
    if request.decision not in allowed_decisions:
        raise HTTPException(
            status_code=422,
            detail="Unsupported decision. Use revalidate, corrected, approved, or rejected.",
        )

    state = {
        "invoice_id": invoice_id,
        "file_path": str(file_path),
        "file_name": invoice["file_name"],
        "workflow_mode": "human_revalidation",
        "thread_id": (
            f"{invoice_id}:revalidation:"
            f"{uuid.uuid4()}"
        ),
        "force_revalidation": True,
        "human_decision": request.decision,
        "human_feedback": request.feedback,
        "human_corrections": request.corrections,
    }

    result = process_invoice(state)
    if result.get("processing_status") == "failed" or result.get("persistence_status") == "failed":
        logger.error(
            "Invoice revalidation failed invoice_id=%s errors=%s",
            invoice_id, result.get("errors") or result.get("persistence_error"),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Invoice revalidation failed; inspect Agent logs.",
                "errors": result.get("errors") or [result.get("persistence_error")],
            },
        )

    return {
        "status": result.get(
            "processing_status"
        ),
        "persistence_status": result.get("persistence_status"),
        "invoice_id": invoice_id,
        "validation_status": result.get(
            "validation_status"
        ),
        "recommendation": result.get(
            "recommendation"
        ),
        "human_review_required": result.get(
            "human_review_required"
        ),
        "discrepancies": result.get(
            "discrepancies",
            [],
        ),
        "warnings": result.get(
            "warnings",
            [],
        ),
        "errors": result.get(
            "errors",
            [],
        ),
        "message": (
            "Invoice revalidated successfully."
        ),
    }


# ------------------------------------------------------------------
# Saved-audit answer fallback (does not depend on Bedrock or Qdrant)
# ------------------------------------------------------------------
def _saved_audit_answer(question: str, invoice_id: str) -> tuple[str, dict[str, Any]] | None:
    """Compose a plain-language answer from authoritative persisted audit facts."""
    invoice = db.fetch_one(
        """SELECT file_name, invoice_number, vendor_name, po_number, currency,
                  total_amount, validation_status, recommendation, human_review_required
           FROM audit.invoices WHERE invoice_id = %s""",
        [invoice_id],
    )
    if not invoice:
        return None
    discrepancies = db.fetch_all(
        """SELECT discrepancy_type, severity, message, details, status
           FROM audit.discrepancies WHERE invoice_id = %s ORDER BY id""",
        [invoice_id],
    )
    lines = db.fetch_all(
        """SELECT line_number, sku, description, quantity, unit_price, line_total
           FROM audit.invoice_line_items WHERE invoice_id = %s ORDER BY line_number""",
        [invoice_id],
    )
    name = invoice.get("file_name") or invoice.get("invoice_number") or "the selected invoice"
    number = invoice.get("invoice_number") or "not extracted"
    status = str(invoice.get("validation_status") or "unknown").replace("_", " ")
    parts = [f"{name} needs manual review because the saved audit record is marked **{status}**."]
    total = invoice.get("total_amount") if invoice.get("total_amount") is not None else "not recorded"
    currency = invoice.get("currency") or "currency not recorded/validated"
    parts.append(f"Invoice **{number}** from **{invoice.get('vendor_name') or 'an unidentified vendor'}**; purchase order **{invoice.get('po_number') or 'not identified'}**; total **{total} {currency}**.")
    if discrepancies:
        parts.append("\n**Recorded discrepancies and what to verify**")
        explanations = {
            "missing_required_field": ("A required invoice field was not extracted or is missing from the saved record.", "Check the original invoice image/PDF for the field and correct the extracted value only if it is clearly present."),
            "currency_not_fully_validated": ("The currency could not be fully confirmed against the reference/ERP data.", "Confirm the currency printed on the invoice and compare it with the purchase order and vendor records."),
            "po_sku_mismatch": ("A line-item SKU did not match a SKU found on the referenced purchase order.", "Compare the invoice line with the PO line and vendor item code; correct the SKU only after checking the source document."),
            "po_unit_price_mismatch": ("The invoice unit price differs from the purchase-order reference or could not be reconciled.", "Compare the invoice unit price, PO unit price, quantity, currency and any approved price change."),
            "po_quantity_mismatch": ("The invoice quantity differs from the PO quantity or expected received quantity.", "Compare invoice quantity with the PO and goods-received record."),
            "missing_erp_record": ("A related vendor, purchase order, or item could not be found in the ERP reference data.", "Verify the identifier on the invoice and confirm the corresponding ERP record exists."),
            "total_mismatch": ("The invoice total does not reconcile with the recorded line items, subtotal, tax or reference total.", "Recalculate line totals and tax from the source invoice and compare with the saved total."),
        }
        for item in discrepancies:
            kind = str(item.get("discrepancy_type") or "validation_issue")
            severity = str(item.get("severity") or "unspecified").upper()
            message = str(item.get("message") or "No detailed message was saved.").strip()
            plain, verify = explanations.get(kind, ("The audit workflow recorded this validation issue.", "Open the original invoice and compare the affected field with the purchase order and ERP reference data."))
            parts.append(f"- **{kind.replace('_', ' ').title()} — {severity}.** {message} {plain} **Verify:** {verify}")
    else:
        parts.append("No discrepancy rows are saved for this invoice. The current review status is recorded, but the underlying reason is not available in the discrepancy table; inspect the audit report and original source before approving it.")
    if lines:
        parts.append("\n**Saved line items**")
        for line in lines:
            parts.append(f"- Line {line.get('line_number')}: SKU `{line.get('sku') or 'unknown'}`; {line.get('description') or 'description not recorded'}; quantity {line.get('quantity')}; unit price {line.get('unit_price')}; line total {line.get('line_total')}.")
    parts.append("\n**Recommended next step:** open the original invoice alongside the purchase order, verify each flagged field, then use Human Review to correct confirmed extraction errors and revalidate. Do not approve solely on the basis of this summary.")
    return "\n\n".join(parts), {"discrepancy_count": len(discrepancies), "line_item_count": len(lines), "source": "saved_audit_database"}


# ------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------
@app.post("/api/query", response_model=QueryResponse)
def query_invoice(request: QueryRequest) -> dict[str, Any]:
    """Answer with hybrid semantic retrieval plus authoritative saved audit facts."""
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if request.invoice_id and not db.fetch_one(
        "SELECT invoice_id FROM audit.invoices WHERE invoice_id = %s",
        [request.invoice_id],
    ):
        raise HTTPException(status_code=404, detail="Selected invoice not found.")

    result: dict[str, Any] = {
        "answer": "", "documents": [], "reflection": {}, "accepted": False,
        "retry_count": 0, "structured_context_used": False, "context": "",
    }
    try:
        from agent.rag.pipeline import run_rag
        result = run_rag(question=question, invoice_id=request.invoice_id)
    except Exception:
        logger.exception("Hybrid RAG pipeline failed; attempting saved audit context")

    answer = str(result.get("answer") or "").strip()
    # If semantic retrieval/evaluation did not produce an answer, make one more
    # grounded attempt using the selected invoice's structured audit facts.
    if not answer and request.invoice_id:
        try:
            from agent.rag.pipeline import _structured_invoice_context
            from agent.rag.generation import generate
            context = _structured_invoice_context(request.invoice_id)
            if context:
                answer = str(generate(question=question, context=context) or "").strip()
                result["context"] = context
                result["structured_context_used"] = True
        except Exception:
            logger.exception("Structured-context answer generation failed")

    if answer:
        structured_used = bool(result.get("structured_context_used"))
        accepted = bool(result.get("accepted"))
        reflection = result.get("reflection") or {}
        if not accepted and not reflection.get("reason"):
            reflection["reason"] = "The answer was generated from available invoice evidence, but the quality evaluator did not approve it. Verify the cited invoice facts before acting."
        return {
            "question": question,
            "invoice_id": request.invoice_id,
            "answer": answer,
            "documents": result.get("documents", []),
            "reflection": reflection,
            "accepted": accepted,
            "retry_count": int(result.get("retry_count", 0)),
            "fallback": structured_used or not accepted,
            "answer_source": "hybrid_rag" if structured_used else "semantic_rag",
            "answer_needs_verification": not accepted,
        }

    # Bedrock generation can fail even when the saved audit facts are present.
    # Answer discrepancy/status questions directly from PostgreSQL rather than
    # retrying a failed model and returning an empty generic response.
    if request.invoice_id:
        try:
            saved_answer = _saved_audit_answer(question, request.invoice_id)
            if saved_answer:
                answer, saved_meta = saved_answer
                return {
                    "question": question,
                    "invoice_id": request.invoice_id,
                    "answer": answer,
                    "documents": result.get("documents", []),
                    "reflection": {},
                    "accepted": True,
                    "retry_count": int(result.get("retry_count", 0)),
                    "fallback": True,
                    "answer_source": "saved_audit_analysis",
                    "answer_needs_verification": True,
                }
        except Exception:
            logger.exception("Saved-audit answer fallback failed")

    # Last-resort, explicit status rather than pretending that a generic list is an answer.
    if request.invoice_id:
        invoice = db.fetch_one(
            """SELECT file_name, invoice_number, vendor_name, validation_status, recommendation
               FROM audit.invoices WHERE invoice_id = %s""",
            [request.invoice_id],
        )
        if invoice:
            answer = (
                f"I couldn't generate a reliable natural-language answer for "
                f"{invoice.get('file_name') or invoice.get('invoice_number') or 'this invoice'}. "
                f"The saved record shows status '{invoice.get('validation_status') or 'unknown'}' "
                f"and recommendation '{invoice.get('recommendation') or 'not recorded'}'. "
                "Try asking about a specific field or discrepancy, or review the invoice details below."
            )
            return {
                "question": question, "invoice_id": request.invoice_id,
                "answer": answer, "documents": result.get("documents", []),
                "reflection": result.get("reflection") or {"reason": "The answer model returned no answer."},
                "accepted": False, "retry_count": int(result.get("retry_count", 0)),
                "fallback": True, "answer_source": "saved_audit_status",
                "answer_needs_verification": True,
            }

    return {
        "question": question, "invoice_id": None,
        "answer": "I couldn't find enough evidence to answer that across all invoices. Select a specific invoice or try a narrower question.",
        "documents": result.get("documents", []),
        "reflection": result.get("reflection") or {"reason": "No sufficient evidence was available."},
        "accepted": False, "retry_count": int(result.get("retry_count", 0)),
        "fallback": False, "answer_source": "insufficient_evidence",
        "answer_needs_verification": True,
    }

# ------------------------------------------------------------------
# Report
# ------------------------------------------------------------------

@app.get(
    "/api/invoices/{invoice_id}/report"
)
def get_invoice_report(
    invoice_id: str,
) -> dict[str, Any]:

    invoice = db.fetch_one(
        """
        SELECT report_path
        FROM audit.invoices
        WHERE invoice_id = %s
        """,
        [invoice_id],
    )

    if not invoice:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    report_path = invoice.get(
        "report_path"
    )

    if not report_path:
        raise HTTPException(
            status_code=404,
            detail="Report not available",
        )

    path = Path(report_path)

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Report file not found",
        )

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to read report: {exc}"
            ),
        ) from exc


# ------------------------------------------------------------------
# Local execution
# ------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent.server:app",
        host=settings.agent_host,
        port=settings.agent_port,
        reload=False,
    )