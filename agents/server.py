import os
import shutil
from pathlib import Path
from uuid import uuid4


import psycopg
from fastapi import FastAPI, File, HTTPException, UploadFile
from psycopg.rows import dict_row


from agents.main import app as workflow_app




app = FastAPI(title="AI Invoice Auditor Agent API")


INCOMING_DIR = Path(os.getenv("INCOMING_DIR", "/app/data/incoming"))
INCOMING_DIR.mkdir(parents=True, exist_ok=True)




def get_connection():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is not configured.")
    return psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
        connect_timeout=5,
    )




def fetch_invoice(invoice_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM audit.invoice_audit WHERE invoice_id = %s",
                (invoice_id,),
            )
            return cur.fetchone()




def save_feedback(invoice_id: str, payload: dict) -> dict:
    field_name = payload.get("field_name") or "general_feedback"
    original_value = payload.get("original_value")
    corrected_value = payload.get("corrected_value")
    corrected_by = payload.get("corrected_by") or "auditor"
    comments = payload.get("comments")


    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit.human_feedback (
                    invoice_id,
                    field_name,
                    original_value,
                    corrected_value,
                    corrected_by,
                    revalidated
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    invoice_id,
                    field_name,
                    str(original_value) if original_value is not None else None,
                    str(corrected_value) if corrected_value is not None else None,
                    corrected_by,
                    False,
                ),
            )
            feedback = cur.fetchone()


    if comments:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE audit.human_feedback
                    SET corrected_value = COALESCE(corrected_value, '') || %s
                    WHERE id = %s
                    """,
                    (f"\n{comments}", feedback["id"]),
                )


    return dict(feedback or {})




@app.get("/health")
def health():
    return {"status": "ok", "service": "agent"}




@app.post("/api/invoices/upload")
async def upload_invoice(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")


    extension = Path(file.filename).suffix.lower()
    if extension not in {".pdf", ".docx", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")


    safe_name = f"{uuid4()}_{file.filename}"
    target_path = INCOMING_DIR / safe_name
    with target_path.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)


    try:
        result = workflow_app.invoke(
            {
                "file_path": str(target_path),
                "file_type": extension,
                "processing_status": "detected",
                "is_duplicate": False,
            }
        )
        return {
            "status": "processed",
            "file_path": str(target_path),
            "invoice_id": result.get("invoice_id"),
            "result": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc




@app.post("/api/invoices/{invoice_id}/feedback")
async def add_feedback(invoice_id: str, payload: dict):
    if not invoice_id:
        raise HTTPException(status_code=400, detail="Invoice ID is required")
    row = save_feedback(invoice_id, payload)
    return {"status": "saved", "invoice_id": invoice_id, "feedback": row}




@app.post("/api/invoices/{invoice_id}/revalidate")
async def revalidate_invoice(invoice_id: str, payload: dict | None = None):
    invoice = fetch_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")


    file_path = invoice.get("file_path")
    if not file_path:
        return {
            "status": "skipped",
            "invoice_id": invoice_id,
            "reason": "No file path is recorded for this invoice.",
        }


    try:
        result = workflow_app.invoke(
            {
                "invoice_id": invoice_id,
                "file_path": file_path,
                "file_type": Path(file_path).suffix.lower(),
                "processing_status": "revalidate",
                "is_duplicate": False,
            }
        )
        return {
            "status": "revalidation_started",
            "invoice_id": invoice_id,
            "result": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc




@app.post("/api/query")
async def ask_query(payload: dict):
    question = (payload or {}).get("question")
    invoice_id = (payload or {}).get("invoice_id")
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")


    invoice = fetch_invoice(invoice_id) if invoice_id else None
    answer = f"I received your question: {question}"
    if invoice:
        answer += f" for invoice {invoice.get('invoice_number') or invoice_id}."


    result = {
        "answer": answer,
        "question": question,
        "invoice_id": invoice_id,
        "score": 0.90,
    }
    return result
