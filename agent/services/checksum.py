from __future__ import annotations

import hashlib
from pathlib import Path


class ChecksumError(Exception):
    """Raised when a file checksum cannot be calculated."""

    pass


def calculate_checksum(
    file_path: str | Path,
    algorithm: str = "sha256",
    chunk_size: int = 1024 * 1024,
) -> str:
    """
    Calculate a checksum for a file.

    The checksum is used to detect duplicate invoices and to ensure
    that the invoice binary has not changed during processing.
    """

    path = Path(file_path)

    if not path.exists():
        raise ChecksumError(
            f"File does not exist: {path}"
        )

    if not path.is_file():
        raise ChecksumError(
            f"Path is not a file: {path}"
        )

    try:
        digest = hashlib.new(algorithm)

        with path.open("rb") as file:
            while True:
                chunk = file.read(chunk_size)

                if not chunk:
                    break

                digest.update(chunk)

        return digest.hexdigest()

    except (OSError, ValueError) as exc:
        raise ChecksumError(
            f"Unable to calculate {algorithm} checksum "
            f"for {path}: {exc}"
        ) from exc


def calculate_sha256(
    file_path: str | Path,
) -> str:
    """Calculate a SHA-256 checksum."""

    return calculate_checksum(
        file_path=file_path,
        algorithm="sha256",
    )


def verify_checksum(
    file_path: str | Path,
    expected_checksum: str,
) -> bool:
    """
    Verify that a file matches the expected checksum.
    """

    if not expected_checksum:
        return False

    actual_checksum = calculate_sha256(
        file_path
    )

    return actual_checksum.lower() == expected_checksum.lower()


def get_file_metadata(
    file_path: str | Path,
) -> dict[str, object]:
    """
    Return basic file metadata used by the invoice workflow.
    """

    path = Path(file_path)

    if not path.exists():
        raise ChecksumError(
            f"File does not exist: {path}"
        )

    if not path.is_file():
        raise ChecksumError(
            f"Path is not a file: {path}"
        )

    try:
        stat = path.stat()

        return {
            "file_name": path.name,
            "file_path": str(path),
            "file_type": path.suffix.lower().lstrip("."),
            "file_size": stat.st_size,
            "file_checksum": calculate_sha256(path),
        }

    except OSError as exc:
        raise ChecksumError(
            f"Unable to read file metadata: {path}"
        ) from exc