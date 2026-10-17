from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field


import uuid

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


logger = logging.getLogger(__name__)


from agent.watcher import InvoiceWatcher
from agent.config import settings
from agent.graph import process_invoice
from agent.services.database import db
from agent.services.erp_client import erp_client
from agent.services.cache import cache

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
)

INCOMING_DIR = Path("/app/data/incoming")
SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".png", ".jpg",
    ".jpeg", ".tiff", ".tif",
}

watcher = InvoiceWatcher(directory=INCOMING_DIR)
watcher_task: asyncio.Task | None = None


class RevalidationRequest(BaseModel):
    corrections: dict[str, Any] = Field(default_factory=dict)
    decision: str | None = None
    feedback: str | None = None


@app.on_event("startup")
async def startup_event():
    global watcher_task
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    watcher_task = asyncio.create_task(watcher.run())


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






@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "database": db.health_check(),
        "erp": erp_client.health_check(),
        "redis": cache.health_check(),
    }


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
def get_invoice(invoice_id: str) -> dict[str, Any]:
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


@app.post("/api/invoices/upload", status_code=202)
async def upload_invoice(file: UploadFile = File(...)):
    """Save an invoice for asynchronous processing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    extension = Path(file.filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {extension or 'unknown'}",
        )

    destination: Path | None = None

    try:
        INCOMING_DIR.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid.uuid4().hex}{extension}"
        destination = INCOMING_DIR / safe_name
        size = 0

        with destination.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break

                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="File exceeds the 25 MB upload limit.",
                    )

                output.write(chunk)

        if size == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )

        logger.info(
            "Invoice uploaded: original=%s stored=%s bytes=%s",
            file.filename,
            safe_name,
            size,
        )

        # InvoiceWatcher is responsible for processing files in this directory.
        return {
            "status": "queued",
            "filename": file.filename,
            "stored_filename": safe_name,
            "size_bytes": size,
            "message": "Upload saved; awaiting invoice processing.",
        }

    except HTTPException:
        if destination is not None:
            destination.unlink(missing_ok=True)
        raise

    except Exception:
        if destination is not None:
            destination.unlink(missing_ok=True)

        logger.exception("Invoice upload failed for %r", file.filename)
        raise HTTPException(
            status_code=500,
            detail="Upload failed. Check the API server logs.",
        )

    finally:
        await file.close()



@app.post("/api/invoices/{invoice_id}/revalidate")
def revalidate_invoice(
    invoice_id: str,
    request: RevalidationRequest,
) -> dict[str, Any]:
    invoice = db.fetch_one(
        """
        SELECT
            invoice_id,
            file_path,
            file_name
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

    file_path = Path(invoice["file_path"])

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Original invoice file no longer exists",
        )

    state: dict[str, Any] = {
        "invoice_id": invoice_id,
        "file_path": str(file_path),
        "file_name": invoice["file_name"],
        "workflow_mode": "human_revalidation",
        "force_revalidation": True,
        "human_decision": request.decision,
        "human_feedback": request.feedback,
        "human_corrections": request.corrections,
    }

    result = process_invoice(state)

    return {
        "status": result.get("processing_status"),
        "invoice_id": invoice_id,
        "validation_status": result.get("validation_status"),
        "recommendation": result.get("recommendation"),
        "human_review_required": result.get(
            "human_review_required"
        ),
        "discrepancies": result.get("discrepancies", []),
        "warnings": result.get("warnings", []),
        "errors": result.get("errors", []),
    }


@app.get("/api/dashboard/summary")
def dashboard_summary() -> dict[str, Any]:
    row = db.fetch_one(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (
                WHERE validation_status = 'approved'
            ) AS approved,
            COUNT(*) FILTER (
                WHERE validation_status = 'manual_review'
            ) AS manual_review,
            COUNT(*) FILTER (
                WHERE validation_status = 'rejected'
            ) AS rejected
        FROM audit.invoices
        """
    )

    return row or {
        "total": 0,
        "approved": 0,
        "manual_review": 0,
        "rejected": 0,
    }


@app.get("/api/invoices/{invoice_id}/report")
def get_invoice_report(invoice_id: str) -> dict[str, Any]:
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

    report_path = invoice.get("report_path")

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
        import json

        return json.loads(path.read_text(encoding="utf-8"))

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to read report: {exc}",
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent.server:app",
        host=settings.agent_host,
        port=settings.agent_port,
        reload=False,
    )