from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from agent.config import settings


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _equal(
    left: Any,
    right: Any,
) -> bool:
    left_value = _decimal(left)
    right_value = _decimal(right)

    if left_value is None or right_value is None:
        return False

    tolerance = Decimal(
        str(settings.amount_tolerance)
    )

    return abs(left_value - right_value) <= tolerance


def _valid_date(value: Any) -> bool:
    if value is None:
        return False

    try:
        date.fromisoformat(str(value))
        return True
    except ValueError:
        return False


def _valid_currency(value: Any) -> bool:
    if value is None:
        return False

    return str(value).strip().upper() in {
        "USD",
        "EUR",
        "GBP",
        "INR",
        "CAD",
        "AUD",
        "JPY",
        "CNY",
        "CHF",
        "SGD",
    }


def _validate_line_totals(
    line_items: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if not line_items:
        return False, ["No invoice line items found."]

    for index, item in enumerate(line_items, start=1):
        quantity = _decimal(
            item.get("quantity")
        )

        unit_price = _decimal(
            item.get("unit_price")
        )

        line_total = _decimal(
            item.get("line_total")
            or item.get("amount")
            or item.get("total")
        )

        if quantity is None:
            errors.append(
                f"Line {index}: quantity is missing or invalid."
            )
            continue

        if unit_price is None:
            errors.append(
                f"Line {index}: unit price is missing or invalid."
            )
            continue

        if line_total is None:
            errors.append(
                f"Line {index}: line total is missing or invalid."
            )
            continue

        expected = quantity * unit_price

        tolerance = Decimal(
            str(settings.amount_tolerance)
        )

        if abs(expected - line_total) > tolerance:
            errors.append(
                f"Line {index}: line total mismatch "
                f"(expected={expected}, actual={line_total})."
            )

    return not errors, errors


def _validate_subtotal(
    line_items: list[dict[str, Any]],
    subtotal: Any,
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    subtotal_value = _decimal(subtotal)

    if subtotal_value is None:
        return False, ["Subtotal is missing or invalid."]

    line_sum = Decimal("0")

    for item in line_items:
        value = _decimal(
            item.get("line_total")
            or item.get("amount")
            or item.get("total")
        )

        if value is not None:
            line_sum += value

    tolerance = Decimal(
        str(settings.amount_tolerance)
    )

    if abs(line_sum - subtotal_value) > tolerance:
        errors.append(
            f"Subtotal mismatch "
            f"(line_sum={line_sum}, subtotal={subtotal_value})."
        )

    return not errors, errors


def _validate_tax(
    subtotal: Any,
    tax: Any,
    tax_rate: Any,
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    subtotal_value = _decimal(subtotal)
    tax_value = _decimal(tax)
    rate_value = _decimal(tax_rate)

    if subtotal_value is None:
        return False, ["Cannot validate tax without subtotal."]

    if tax_value is None:
        return False, ["Tax amount is missing or invalid."]

    if rate_value is None:
        return False, ["Tax rate is missing or invalid."]

    expected_tax = (
        subtotal_value
        * rate_value
        / Decimal("100")
    )

    tolerance = Decimal(
        str(settings.amount_tolerance)
    )

    if abs(expected_tax - tax_value) > tolerance:
        errors.append(
            f"Tax mismatch "
            f"(expected={expected_tax}, tax={tax_value}, "
            f"rate={rate_value}%)."
        )

    return not errors, errors


def _validate_total(
    subtotal: Any,
    tax: Any,
    total: Any,
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    subtotal_value = _decimal(subtotal)
    tax_value = _decimal(tax)
    total_value = _decimal(total)

    if subtotal_value is None:
        return False, ["Cannot validate total without subtotal."]

    if tax_value is None:
        return False, ["Cannot validate total without tax."]

    if total_value is None:
        return False, ["Total is missing or invalid."]

    expected_total = (
        subtotal_value + tax_value
    )

    tolerance = Decimal(
        str(settings.amount_tolerance)
    )

    if abs(expected_total - total_value) > tolerance:
        errors.append(
            f"Total mismatch "
            f"(expected={expected_total}, total={total_value})."
        )

    return not errors, errors


def data_validate(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate the internal mathematical and structural consistency
    of extracted invoice data.

    This is independent of ERP/business validation.
    """

    invoice_number = (
        state.get("effective_invoice_number")
        or state.get("extracted_invoice_number")
    )

    vendor_name = (
        state.get("effective_vendor_name")
        or state.get("extracted_vendor_name")
    )

    invoice_date = (
        state.get("effective_invoice_date")
        or state.get("extracted_invoice_date")
    )

    currency = (
        state.get("effective_currency")
        or state.get("extracted_currency")
    )

    subtotal = (
        state.get("effective_subtotal_amount")
        if state.get("effective_subtotal_amount") is not None
        else state.get("extracted_subtotal_amount")
    )

    tax = (
        state.get("effective_tax_amount")
        if state.get("effective_tax_amount") is not None
        else state.get("extracted_tax_amount")
    )

    tax_rate = (
        state.get("effective_tax_rate")
        if state.get("effective_tax_rate") is not None
        else state.get("extracted_tax_rate")
    )

    total = (
        state.get("effective_total_amount")
        if state.get("effective_total_amount") is not None
        else state.get("extracted_total_amount")
    )

    line_items = (
        state.get("effective_line_items")
        or state.get("extracted_line_items")
        or state.get("line_items")
        or []
    )

    errors: list[str] = []
    warnings: list[str] = []

    # ------------------------------------------------------------
    # Required fields
    # ------------------------------------------------------------

    required_values = {
        "invoice_number": invoice_number,
        "vendor_name": vendor_name,
        "invoice_date": invoice_date,
        "currency": currency,
        "subtotal_amount": subtotal,
        "tax_amount": tax,
        "total_amount": total,
    }

    missing_fields = [
        name
        for name, value in required_values.items()
        if value is None
        or (
            isinstance(value, str)
            and not value.strip()
        )
    ]

    required_fields_valid = not missing_fields

    if missing_fields:
        errors.append(
            "Missing required fields: "
            + ", ".join(missing_fields)
        )

    # ------------------------------------------------------------
    # Date
    # ------------------------------------------------------------

    date_valid = _valid_date(
        invoice_date
    )

    if invoice_date and not date_valid:
        errors.append(
            f"Invalid invoice date: {invoice_date}"
        )

    # ------------------------------------------------------------
    # Currency
    # ------------------------------------------------------------

    currency_valid = _valid_currency(
        currency
    )

    if currency and not currency_valid:
        errors.append(
            f"Unsupported or invalid currency: {currency}"
        )

    # ------------------------------------------------------------
    # Line totals
    # ------------------------------------------------------------

    line_totals_valid, line_errors = (
        _validate_line_totals(
            line_items
        )
    )

    errors.extend(line_errors)

    # ------------------------------------------------------------
    # Subtotal
    # ------------------------------------------------------------

    subtotal_valid, subtotal_errors = (
        _validate_subtotal(
            line_items,
            subtotal,
        )
    )

    errors.extend(subtotal_errors)

    # ------------------------------------------------------------
    # Tax
    # ------------------------------------------------------------

    tax_valid, tax_errors = _validate_tax(
        subtotal,
        tax,
        tax_rate,
    )

    errors.extend(tax_errors)

    # ------------------------------------------------------------
    # Total
    # ------------------------------------------------------------

    total_valid, total_errors = _validate_total(
        subtotal,
        tax,
        total,
    )

    errors.extend(total_errors)

    # ------------------------------------------------------------
    # Final result
    # ------------------------------------------------------------

    data_validation_passed = (
        required_fields_valid
        and date_valid
        and currency_valid
        and line_totals_valid
        and subtotal_valid
        and tax_valid
        and total_valid
        and not errors
    )

    if not data_validation_passed:
        warnings.append(
            "Invoice requires manual review because "
            "one or more data validation checks failed."
        )

    return {
        "required_fields_valid": required_fields_valid,
        "line_totals_valid": line_totals_valid,
        "subtotal_valid": subtotal_valid,
        "tax_valid": tax_valid,
        "total_valid": total_valid,
        "date_valid": date_valid,
        "currency_valid": currency_valid,
        "data_validation_passed": data_validation_passed,
        "data_validation_errors": errors,
        "data_validation_warnings": warnings,
        "validation_errors": errors,
        "validation_warnings": warnings,
        "missing_fields": missing_fields,
        "human_review_required": not data_validation_passed,
        "processing_status": "data_validation_complete",
    }