from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.config import settings
from agent.services.checksum import (
    ChecksumError,
    get_file_metadata,
)
from agent.services.database import db, DatabaseErrorHandler


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
}


def monitor_invoice(state: dict[str, Any]) -> dict[str, Any]:
    """
    Monitor and initialize invoice processing metadata.

    This node:
    - validates the incoming file
    - calculates its checksum
    - detects duplicate processing
    - initializes workflow state

    It does not extract invoice content.
    """

    file_path = state.get("file_path")

    if not file_path:
        return {
            "processing_status": "failed",
            "errors": ["Invoice file path is missing."],
        }

    path = Path(file_path)

    if not path.exists():
        return {
            "processing_status": "failed",
            "errors": [f"Invoice file does not exist: {path}"],
        }

    if not path.is_file():
        return {
            "processing_status": "failed",
            "errors": [f"Invoice path is not a file: {path}"],
        }

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return {
            "processing_status": "failed",
            "errors": [
                f"Unsupported invoice file type: {path.suffix}"
            ],
        }

    try:
        metadata = get_file_metadata(path)
    except ChecksumError as exc:
        return {
            "processing_status": "failed",
            "errors": [str(exc)],
        }

    checksum = str(metadata["file_checksum"])

    # Explicit revalidation is allowed to reuse the original file checksum.
    force_revalidation = bool(state.get("force_revalidation", False))
    duplicate_record = None
    if not force_revalidation:
        try:
            duplicate_record = db.fetch_one(
                "SELECT invoice_id FROM audit.invoices WHERE file_checksum = %s LIMIT 1",
                [checksum],
            )
        except DatabaseErrorHandler as exc:
            return {
                **metadata,
                "file_path": str(path.resolve()),
                "file_checksum": checksum,
                "processing_status": "failed",
                "errors": [f"Unable to check invoice checksum in audit database: {exc}"],
            }

    # Do not compare state["file_checksum"] with this computed checksum:
    # the watcher passes the current file's checksum in state, so that
    # comparison would incorrectly classify every new upload as a duplicate.
    is_duplicate = bool(duplicate_record) and not force_revalidation

    errors = list(state.get("errors") or [])
    warnings = list(state.get("warnings") or [])

    if is_duplicate:
        warnings.append(f"Duplicate invoice detected for checksum {checksum}.")

    return {
        "file_path": str(path.resolve()),
        "file_name": metadata["file_name"],
        "file_type": metadata["file_type"],
        "file_size": metadata["file_size"],
        "file_checksum": checksum,
        "is_duplicate": is_duplicate,
        "processing_status": (
            "duplicate"
            if is_duplicate
            else "monitoring_complete"
        ),
        "errors": errors,
        "warnings": warnings,
    }


def scan_incoming_directory() -> list[dict[str, Any]]:
    """
    Discover supported invoice files in data/incoming.

    Files are returned as metadata dictionaries. Processing itself is
    performed by the workflow, not by this function.
    """

    incoming_dir = Path(settings.incoming_dir)

    if not incoming_dir.exists():
        incoming_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        return []

    invoices: list[dict[str, Any]] = []

    for path in sorted(incoming_dir.iterdir()):

        if not path.is_file():
            continue

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        try:
            metadata = get_file_metadata(path)
        except ChecksumError:
            continue

        invoices.append(metadata)

    return invoices