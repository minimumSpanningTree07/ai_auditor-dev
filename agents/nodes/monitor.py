from pathlib import Path
from uuid import uuid4
import hashlib
import os

import psycopg
from psycopg.rows import dict_row

from agents.state import InvoiceState


INCOMING_DIR = Path(
    os.getenv("INCOMING_DIR", "/app/data/incoming")
)

SUPPORTED_TYPES = {".pdf", ".docx", ".png", ".jpg", ".jpeg"}


def get_connection():
    """Create a PostgreSQL connection."""
    return psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
    )


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA-256 without loading the whole file into memory."""
    checksum = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            checksum.update(chunk)

    return checksum.hexdigest()


def record_failure(
    path: Path,
    checksum: str | None,
    extension: str,
    message: str,
) -> None:
    """Record a file-processing failure in audit.file_monitor."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit.file_monitor (
                        file_path,
                        file_checksum,
                        file_type,
                        processing_status,
                        error_message
                    )
                    VALUES (%s, %s, %s, 'failed', %s)
                    ON CONFLICT (file_path, file_checksum)
                    DO UPDATE SET
                        processing_status = 'failed',
                        error_message = EXCLUDED.error_message,
                        updated_at = now()
                    """,
                    (
                        str(path),
                        checksum,
                        extension,
                        message,
                    ),
                )
    except Exception as db_error:
        print(
            f"Could not record failure for {path}: {db_error}"
        )


def monitor_node(state: InvoiceState) -> dict:
    """
    Prepare the requested file or find the next incoming file.

    - Reuse the original invoice UUID for an audited duplicate.
    - Generate a UUID for a new invoice.
    - Record file detection in audit.file_monitor.
    """

    INCOMING_DIR.mkdir(parents=True, exist_ok=True)

    requested_path = state.get("file_path")

    if requested_path:
        candidates = [Path(requested_path)]
    else:
        candidates = sorted(INCOMING_DIR.iterdir())

    for candidate in candidates:
        if not candidate.is_file():
            continue

        path = candidate.resolve()
        extension = path.suffix.lower()
        checksum = None

        if extension not in SUPPORTED_TYPES:
            continue

        try:
            checksum = calculate_checksum(path)

            with get_connection() as conn:
                with conn.cursor() as cur:

                    # 1. Look for an existing completed audit.
                    cur.execute(
                        """
                        SELECT invoice_id
                        FROM audit.invoice_audit
                        WHERE file_checksum = %s
                        """,
                        (checksum,),
                    )
                    existing_audit = cur.fetchone()

                    if existing_audit:
                        original_invoice_id = str(
                            existing_audit["invoice_id"]
                        )

                        # Record this file as a duplicate.
                        cur.execute(
                            """
                            INSERT INTO audit.file_monitor (
                                file_path,
                                file_checksum,
                                file_type,
                                processing_status,
                                error_message
                            )
                            VALUES (
                                %s, %s, %s, 'duplicate', NULL
                            )
                            ON CONFLICT (file_path, file_checksum)
                            DO UPDATE SET
                                processing_status = 'duplicate',
                                error_message = NULL,
                                updated_at = now()
                            """,
                            (
                                str(path),
                                checksum,
                                extension,
                            ),
                        )

                        return {
                            "invoice_id": original_invoice_id,
                            "duplicate_invoice_id": original_invoice_id,
                            "file_path": str(path),
                            "file_type": extension,
                            "file_checksum": checksum,
                            "is_duplicate": True,
                            "processing_status": "duplicate",
                            "current_stage": "monitor_completed",
                        }

                    # 2. Reuse an invoice ID already present in state,
                    # otherwise generate one for this new invoice.
                    invoice_id = (
                        state.get("invoice_id") or str(uuid4())
                    )

                    # 3. Register the new detection.
                    cur.execute(
                        """
                        INSERT INTO audit.file_monitor (
                            file_path,
                            file_checksum,
                            file_type,
                            processing_status,
                            error_message
                        )
                        VALUES (
                            %s, %s, %s, 'detected', NULL
                        )
                        ON CONFLICT (file_path, file_checksum)
                        DO UPDATE SET
                            processing_status = 'detected',
                            error_message = NULL,
                            updated_at = now()
                        """,
                        (
                            str(path),
                            checksum,
                            extension,
                        ),
                    )

            return {
                "invoice_id": invoice_id,
                "file_path": str(path),
                "file_type": extension,
                "file_checksum": checksum,
                "is_duplicate": False,
                "duplicate_invoice_id": None,
                "processing_status": "detected",
                "current_stage": "monitor_completed",
            }

        except Exception as exc:
            record_failure(
                path,
                checksum,
                extension,
                str(exc),
            )

            if requested_path:
                return {
                    "file_path": str(path),
                    "file_checksum": checksum,
                    "file_type": extension,
                    "processing_status": "failed",
                    "error_message": str(exc),
                    "current_stage": "monitor_failed",
                }

    return {
        "processing_status": "idle",
        "current_stage": "monitor_idle",
    }

