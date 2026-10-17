from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agent.config import settings


SUPPORTED_TEXT_EXTENSIONS = {
    ".txt",
    ".csv",
    ".json",
    ".xml",
    ".html",
    ".md",
}

SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
}


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_text_file(path: Path) -> str:
    return _clean_text(
        path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    )


def _extract_pdf_text(path: Path) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required for PDF extraction."
        ) from exc

    pages: list[str] = []

    with fitz.open(path) as document:
        for page in document:
            text = page.get_text("text")

            if text:
                pages.append(text)

    return _clean_text("\n".join(pages))


def _extract_ocr_text(path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Pillow and pytesseract are required for OCR."
        ) from exc

    language = settings.ocr_languages or "eng"

    image = Image.open(path)

    return _clean_text(
        pytesseract.image_to_string(
            image,
            lang=language,
        )
    )



def _extract_docx_text(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("python-docx is required for DOCX extraction.") from exc
    document = Document(str(path))
    parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return _clean_text("\n".join(parts))

def _extract_document_text(path: Path) -> tuple[str, str]:
    """
    Return extracted text and extraction method.
    """

    suffix = path.suffix.lower()

    if suffix in SUPPORTED_TEXT_EXTENSIONS:
        return _extract_text_file(path), "text"

    if suffix == ".docx":
        text = _extract_docx_text(path)
        return text, "docx"

    if suffix == ".pdf":
        text = _extract_pdf_text(path)

        if text:
            return text, "pdf_text"

        if settings.ocr_enabled:
            return _extract_ocr_text(path), "ocr"

        return "", "pdf_text"

    if suffix in {
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
    }:
        if not settings.ocr_enabled:
            return "", "ocr_disabled"

        return _extract_ocr_text(path), "ocr"

    raise ValueError(
        f"Unsupported extraction format: {suffix}"
    )


def _estimate_confidence(
    text: str,
    extraction_method: str,
) -> float:
    """
    Estimate extraction confidence from the presence of
    invoice-specific information.

    This is intentionally deterministic and does not call an LLM.
    """

    if not text:
        return 0.0

    score = 0.4

    patterns = [
        r"\binvoice\b",
        r"\btotal\b",
        r"\bdate\b",
        r"\b(?:po|purchase\s+order)\b",
        r"\b(?:tax|vat|gst)\b",
    ]

    matches = sum(
        bool(re.search(pattern, text, re.IGNORECASE))
        for pattern in patterns
    )

    score += matches * 0.1

    if extraction_method == "pdf_text":
        score += 0.05

    return round(
        min(score, 1.0),
        3,
    )


def extract_invoice(state: dict[str, Any]) -> dict[str, Any]:
    """
    Extract raw invoice text.

    Field-level extraction is deliberately handled by the next
    field_extraction node.
    """

    file_path = state.get("file_path")

    if not file_path:
        return {
            "processing_status": "failed",
            "errors": [
                "Invoice file path is missing."
            ],
        }

    path = Path(file_path)

    if not path.exists():
        return {
            "processing_status": "failed",
            "errors": [
                f"Invoice file does not exist: {path}"
            ],
        }

    try:
        text, method = _extract_document_text(path)

    except Exception as exc:
        return {
            "extraction_method": "failed",
            "extraction_confidence": 0.0,
            "extraction_errors": [str(exc)],
            "processing_status": "failed",
            "errors": [
                f"Invoice extraction failed: {exc}"
            ],
        }

    if not text:
        return {
            "extraction_method": method,
            "raw_extracted_text": "",
            "extraction_confidence": 0.0,
            "extraction_errors": [
                "No text could be extracted from the invoice."
            ],
            "processing_status": "failed",
            "errors": [
                "Invoice contains no extractable text."
            ],
        }

    confidence = _estimate_confidence(
        text,
        method,
    )

    return {
        "extraction_method": method,
        "raw_extracted_text": text,
        "extraction_confidence": confidence,
        "extraction_errors": [],
        "processing_status": "extraction_complete",
    }