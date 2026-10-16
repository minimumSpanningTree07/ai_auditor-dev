from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any


MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


def _parse_decimal(value: str | None) -> float | None:
    if not value:
        return None

    cleaned = value.strip()
    cleaned = re.sub(r"[^\d,.\-]", "", cleaned)

    if not cleaned:
        return None

    # Handle formats such as 1,470.50 and 1.470,50.
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "")
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    elif "," in cleaned:
        parts = cleaned.split(",")

        if len(parts[-1]) == 2:
            cleaned = "".join(parts[:-1]) + "." + parts[-1]
        else:
            cleaned = cleaned.replace(",", "")

    try:
        return float(Decimal(cleaned))
    except (InvalidOperation, ValueError):
        return None


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None

    value = value.strip()

    # YYYY-MM-DD / YYYY/MM/DD
    match = re.fullmatch(
        r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
        value,
    )

    if match:
        try:
            return date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            ).isoformat()
        except ValueError:
            return None

    # DD-MM-YYYY / DD/MM/YYYY
    match = re.fullmatch(
        r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})",
        value,
    )

    if match:
        try:
            return date(
                int(match.group(3)),
                int(match.group(2)),
                int(match.group(1)),
            ).isoformat()
        except ValueError:
            return None

    # 14 March 2025 / 14 Mar 2025
    match = re.fullmatch(
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
        value,
    )

    if match:
        month = MONTHS.get(
            match.group(2).lower()
        )

        if month:
            try:
                return date(
                    int(match.group(3)),
                    month,
                    int(match.group(1)),
                ).isoformat()
            except ValueError:
                return None

    # March 14, 2025
    match = re.fullmatch(
        r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})",
        value,
    )

    if match:
        month = MONTHS.get(
            match.group(1).lower()
        )

        if month:
            try:
                return date(
                    int(match.group(3)),
                    month,
                    int(match.group(2)),
                ).isoformat()
            except ValueError:
                return None

    return None


def _find_value(
    text: str,
    patterns: list[str],
) -> str | None:
    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE | re.MULTILINE,
        )

        if match:
            value = match.group(1).strip()

            if value:
                return value

    return None


def _extract_vendor(
    lines: list[str],
) -> str | None:
    ignored = {
        "invoice",
        "invoice no",
        "invoice number",
        "invoice date",
        "date",
        "po reference",
        "purchase order",
        "subtotal",
        "tax",
        "total",
        "description",
        "quantity",
        "qty",
        "unit price",
        "amount",
    }

    for line in lines[:8]:
        normalized = re.sub(
            r"[:#\-]+$",
            "",
            line,
        ).strip()

        if not normalized:
            continue

        lower = normalized.lower()

        if any(
            lower.startswith(item)
            for item in ignored
        ):
            continue

        if re.search(
            r"\b(invoice|date|total|tax|subtotal|po|purchase order)\b",
            lower,
        ):
            continue

        if re.search(
            r"\d{2,}",
            normalized,
        ):
            continue

        if len(normalized) >= 3:
            return normalized

    return None


def _extract_currency(
    text: str,
) -> str | None:
    currency_patterns = [
        (r"\bUSD\b", "USD"),
        (r"\bEUR\b", "EUR"),
        (r"\bGBP\b", "GBP"),
        (r"\bINR\b", "INR"),
        (r"\bCAD\b", "CAD"),
        (r"\bAUD\b", "AUD"),
        (r"\bJPY\b", "JPY"),
        (r"\$", "USD"),
        (r"€", "EUR"),
        (r"£", "GBP"),
        (r"₹", "INR"),
    ]

    for pattern, currency in currency_patterns:
        if re.search(
            pattern,
            text,
            re.IGNORECASE,
        ):
            return currency

    return None


def _extract_line_items(
    text: str,
) -> list[dict[str, Any]]:
    """
    Parse common invoice table formats.

    Expected examples:

        Widget A    2    100.00    200.00
        SKU-001     2    100.00    200.00

    Header lines and summary lines are ignored.
    """

    items: list[dict[str, Any]] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        lower = line.lower()

        if any(
            keyword in lower
            for keyword in (
                "description",
                "subtotal",
                "tax",
                "total",
                "invoice no",
                "invoice date",
                "po reference",
                "purchase order",
            )
        ):
            continue

        match = re.match(
            r"^(?P<description>.+?)"
            r"\s+(?P<quantity>\d+(?:[.,]\d+)?)"
            r"\s+(?P<unit_price>[$€£₹]?\s*[\d,]+(?:\.\d+)?)"
            r"\s+(?P<amount>[$€£₹]?\s*[\d,]+(?:\.\d+)?)$",
            line,
        )

        if not match:
            continue

        description = match.group(
            "description"
        ).strip()

        quantity = _parse_decimal(
            match.group("quantity")
        )

        unit_price = _parse_decimal(
            match.group("unit_price")
        )

        amount = _parse_decimal(
            match.group("amount")
        )

        if (
            not description
            or quantity is None
            or unit_price is None
            or amount is None
        ):
            continue

        items.append(
            {
                "description": description,
                "sku": None,
                "quantity": quantity,
                "unit_price": unit_price,
                "amount": amount,
                "line_total": amount,
            }
        )

    return items


def extract_fields(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Extract structured invoice fields from translated text.

    Original raw text remains untouched.
    """

    text = (
        state.get("translated_text")
        or state.get("raw_extracted_text")
        or ""
    )

    if not text:
        return {
            "processing_status": "failed",
            "errors": [
                "No invoice text available for field extraction."
            ],
        }

    lines = _lines(text)

    invoice_number = _find_value(
        text,
        [
            r"^\s*invoice\s*(?:no|number|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9./_-]*)\s*$",
            r"\binvoice\s*(?:no|number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9./_-]*)",
        ],
    )

    po_number = _find_value(
        text,
        [
            r"^\s*(?:po|purchase\s+order)"
            r"(?:\s*(?:no|number|reference|ref|#))?"
            r"\s*[:\-]?\s*([A-Z0-9][A-Z0-9./_-]*)\s*$",
            r"\bPO\s*(?:Reference|Ref|No|Number|#)?"
            r"\s*[:\-]?\s*([A-Z0-9][A-Z0-9./_-]*)",
        ],
    )

    date_value = _find_value(
        text,
        [
            r"^\s*(?:invoice\s+)?date\s*[:\-]?\s*"
            r"([0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4})\s*$",
            r"^\s*(?:invoice\s+)?date\s*[:\-]?\s*"
            r"([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})\s*$",
            r"^\s*(?:invoice\s+)?date\s*[:\-]?\s*"
            r"([A-Za-z]+\s+[0-9]{1,2},?\s+[0-9]{4})\s*$",
        ],
    )

    subtotal_raw = _find_value(
        text,
        [
            r"^\s*subtotal\s*[:\-]?\s*"
            r"([$€£₹]?\s*[\d,]+(?:\.\d+)?)\s*$",
        ],
    )

    tax_raw = _find_value(
        text,
        [
            r"^\s*(?:tax|vat|gst)\s*[:\-]?\s*"
            r"([$€£₹]?\s*[\d,]+(?:\.\d+)?)\s*$",
        ],
    )

    total_raw = _find_value(
        text,
        [
            r"^\s*(?:grand\s+)?total\s*[:\-]?\s*"
            r"([$€£₹]?\s*[\d,]+(?:\.\d+)?)\s*$",
        ],
    )

    tax_rate_raw = _find_value(
        text,
        [
            r"(?:tax|vat|gst)\s*(?:rate)?\s*[:\-]?\s*"
            r"(\d+(?:\.\d+)?)\s*%",
        ],
    )

    tax_amount = _parse_decimal(tax_raw)
    subtotal_amount = _parse_decimal(subtotal_raw)
    total_amount = _parse_decimal(total_raw)

    tax_rate = _parse_decimal(tax_rate_raw)

    if (
        tax_rate is None
        and subtotal_amount not in (None, 0)
        and tax_amount is not None
    ):
        tax_rate = round(
            (tax_amount / subtotal_amount) * 100,
            4,
        )

    line_items = _extract_line_items(text)

    errors: list[str] = []

    if not invoice_number:
        errors.append("Invoice number could not be extracted.")

    if not po_number:
        errors.append("PO number could not be extracted.")

    if not date_value:
        errors.append("Invoice date could not be extracted.")

    return {
        "extracted_invoice_number": invoice_number,
        "extracted_vendor_name": _extract_vendor(lines),
        "extracted_po_number": po_number,
        "extracted_invoice_date": _parse_date(date_value),
        "extracted_currency": _extract_currency(text),
        "extracted_subtotal_amount": subtotal_amount,
        "extracted_tax_amount": tax_amount,
        "extracted_tax_rate": tax_rate,
        "extracted_total_amount": total_amount,
        "extracted_line_items": line_items,
        "line_items": line_items,
        "validation_errors": errors,
        "missing_fields": [
            field
            for field, value in {
                "invoice_number": invoice_number,
                "vendor_name": _extract_vendor(lines),
                "po_number": po_number,
                "invoice_date": _parse_date(date_value),
                "currency": _extract_currency(text),
                "subtotal_amount": subtotal_amount,
                "tax_amount": tax_amount,
                "total_amount": total_amount,
            }.items()
            if value is None
        ],
        "processing_status": "field_extraction_complete",
    }