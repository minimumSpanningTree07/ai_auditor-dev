
from pathlib import Path
import hashlib
import os

import psycopg
from psycopg.rows import dict_row

from agents.state import InvoiceState


INCOMING_DIR = Path(
    os.getenv("INCOMING_DIR", "/app/data/incoming")
)
#INCOMING_DIR = Path("/home/labuser/aug26-sp1-l1-fa3-proj-group-38/data/incoming")

SUPPORTED_TYPES = {".pdf", ".docx", ".png", ".jpg", ".jpeg"}


def get_connection():
    return psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
    )


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA-256 without loading the entire file into memory."""
    checksum = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            checksum.update(chunk)

    return checksum.hexdigest()




def monitor_node(state: InvoiceState) -> dict:
    """Prepare the specific requested file, or find the next file."""

    INCOMING_DIR.mkdir(parents=True, exist_ok=True)

    # Prefer the file supplied by watcher.py.
    requested_path = state.get("file_path")

    if requested_path:
        candidates = [Path(requested_path)]
    else:
        candidates = sorted(INCOMING_DIR.iterdir())

    for path in candidates:
        if not path.is_file():
            continue

        path = path.resolve()
        checksum = None
        extension = path.suffix.lower()

        try:
            if extension not in SUPPORTED_TYPES:
                continue

            checksum = calculate_checksum(path)

            with get_connection() as conn:
                with conn.cursor() as cur:

                    # Skip only if this file has already been audited.
                    cur.execute(
                        """
                        SELECT invoice_id
                        FROM audit.invoice_audit
                        WHERE file_checksum = %s
                        """,
                        (checksum,),
                    )
                    duplicate = cur.fetchone()

                    if duplicate:
                        cur.execute(
                            """
                            INSERT INTO audit.file_monitor
                                (file_path, file_checksum, file_type,
                                 processing_status)
                            VALUES (%s, %s, %s, 'duplicate')
                            ON CONFLICT (file_path, file_checksum)
                            DO UPDATE SET
                                processing_status = 'duplicate',
                                updated_at = now()
                            """,
                            (str(path), checksum, extension),
                        )

                        return {
                            "file_path": str(path),
                            "file_type": extension,
                            "file_checksum": checksum,
                            "is_duplicate": True,
                            "duplicate_invoice_id": str(
                                duplicate["invoice_id"]
                            ),
                            "processing_status": "duplicate",
                            "current_stage": "monitor_completed",
                        }

                    # Insert or reset an incomplete monitoring record.
                    cur.execute(
                        """
                        INSERT INTO audit.file_monitor
                            (file_path, file_checksum, file_type,
                             processing_status, error_message)
                        VALUES (%s, %s, %s, 'detected', NULL)
                        ON CONFLICT (file_path, file_checksum)
                        DO UPDATE SET
                            processing_status = 'detected',
                            error_message = NULL,
                            updated_at = now()
                        """,
                        (str(path), checksum, extension),
                    )

            return {
                "file_path": str(path),
                "file_type": extension,
                "file_checksum": checksum,
                "is_duplicate": False,
                "processing_status": "detected",
                "current_stage": "monitor_completed",
            }

        except Exception as exc:
            record_failure(path, checksum, extension, str(exc))

            # If the watcher supplied this file, expose the failure.
            if requested_path:
                return {
                    "file_path": str(path),
                    "file_checksum": checksum,
                    "processing_status": "failed",
                    "error_message": str(exc),
                    "current_stage": "monitor_failed",
                }

    return {
        "processing_status": "idle",
        "current_stage": "monitor_idle",
    }

def record_failure(path, checksum, extension, message):
    """Record a file that could not be prepared for processing."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit.file_monitor
                        (file_path, file_checksum, file_type,
                         processing_status, error_message)
                    VALUES (%s, %s, %s, 'failed', %s)
                    ON CONFLICT (file_path, file_checksum)
                    DO UPDATE SET
                        processing_status = 'failed',
                        error_message = EXCLUDED.error_message,
                        updated_at = now()
                    """,
                    (str(path), checksum, extension, message),
                )
    except Exception as db_error:
        # The database itself may be unavailable.
        print(f"Could not record failure for {path}: {db_error}")

