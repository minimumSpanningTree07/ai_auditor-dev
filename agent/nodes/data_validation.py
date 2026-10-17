
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
import re

from agent.config import settings


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _effective(state: dict[str, Any], field: str) -> Any:
    """
    Prefer human-corrected effective values, then canonical state values,
    and finally immutable original extraction values.
    """
    effective_value = state.get(f"effective_{field}")
    if effective_value is not None:
        return effective_value

    canonical_value = state.get(field)
    if canonical_value is not None:
        return canonical_value

    return state.get(f"extracted_{field}")


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None

    if isinstance(value, Decimal):
        return value

    try:
        normalized = str(value).strip().replace(",", "")
        normalized = re.sub(r"^[^\d+\-.]+", "", normalized)
        normalized = re.sub(r"[^\d.\-+]+$", "", normalized)

        if not normalized:
            return None

        return Decimal(normalized)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    # Prefer unambiguous date formats. Do not guess ambiguous
    # values such as 03/04/2026.
    formats = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%d %b %Y",
        "%d %B %Y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.date()
    except ValueError:
        return None


def _amount_tolerance() -> Decimal:
    try:
        return Decimal(str(settings.amount_tolerance))
    except (AttributeError, InvalidOperation, TypeError, ValueError):
        return Decimal("0.02")


def _add_discrepancy(
    discrepancies: list[dict[str, Any]],
    *,
    discrepancy_type: str,
    message: str,
    severity: str = "high",
    details: dict[str, Any] | None = None,
) -> None:
    """
    Keep the existing discrepancy keys consumed by persistence:
    type, severity, message, details, status.
    """
    discrepancies.append(
        {
            "type": discrepancy_type,
            "severity": severity,
            "message": message,
            "details": details or {},
            "status": "open",
        }
    )


# ---------------------------------------------------------------------
# Data validation
# ---------------------------------------------------------------------

def data_validate(state: dict[str, Any]) -> dict[str, Any]:
    """
    Validate invoice completeness, field formats and arithmetic.

    This node does not query the ERP. ERP vendor, PO, SKU, quantity and
    unit-price checks belong in business_validation.py.

    Original extracted_* fields are read-only. This function validates
    the effective/corrected values and returns validation results for
    the existing InvoiceState.
    """
    errors: list[str] = []
    warnings: list[str] = []
    discrepancies: list[dict[str, Any]] = []

    invoice_number = _effective(state, "invoice_number")
    vendor_name = _effective(state, "vendor_name")
    po_number = _effective(state, "po_number")
    invoice_date_value = _effective(state, "invoice_date")
    currency = _effective(state, "currency")
    subtotal_value = _effective(state, "subtotal_amount")
    tax_value = _effective(state, "tax_amount")
    tax_rate_value = _effective(state, "tax_rate")
    total_value = _effective(state, "total_amount")
    line_items = _effective(state, "line_items") or []

    # -------------------------------------------------------------
    # Required fields
    # -------------------------------------------------------------

    required_values = {
        "invoice_number": invoice_number,
        "vendor_name": vendor_name,
        "invoice_date": invoice_date_value,
        "currency": currency,
        "total_amount": total_value,
    }

    missing_fields: list[str] = []

    for field, value in required_values.items():
        if value is None or not _normalize_text(value):
            missing_fields.append(field)

    if not line_items:
        missing_fields.append("line_items")

    required_fields_valid = not missing_fields

    for field in missing_fields:
        message = f"Required invoice field is missing: {field}."
        errors.append(message)
        _add_discrepancy(
            discrepancies,
            discrepancy_type="missing_required_field",
            message=message,
            severity="high",
            details={"field": field},
        )

    # A PO number can be mandatory for the business process, but it
    # is kept separate from the basic data-completeness check so that
    # the workflow can distinguish missing invoice data from an ERP
    # or purchasing-process issue.
    if not po_number:
        message = "Purchase order number is missing."
        warnings.append(message)
        _add_discrepancy(
            discrepancies,
            discrepancy_type="missing_purchase_order",
            message=message,
            severity="high",
            details={"field": "po_number"},
        )

    # -------------------------------------------------------------
    # Date validation
    # -------------------------------------------------------------

    parsed_invoice_date = _parse_date(invoice_date_value)
    date_valid = parsed_invoice_date is not None

    if invoice_date_value and not date_valid:
        message = (
            f"Invoice date '{invoice_date_value}' could not be parsed "
            "unambiguously."
        )
        errors.append(message)
        _add_discrepancy(
            discrepancies,
            discrepancy_type="invalid_invoice_date",
            message=message,
            details={"value": str(invoice_date_value)},
        )

    if parsed_invoice_date and parsed_invoice_date > date.today():
        message = (
            f"Invoice date {parsed_invoice_date.isoformat()} is in the future."
        )
        warnings.append(message)
        _add_discrepancy(
            discrepancies,
            discrepancy_type="future_invoice_date",
            message=message,
            severity="medium",
            details={"value": parsed_invoice_date.isoformat()},
        )

    # -------------------------------------------------------------
    # Currency validation
    # -------------------------------------------------------------

    normalized_currency = _normalize_text(currency).upper()

    # ISO 4217 codes are normally three uppercase letters. This checks
    # format only; ERP currency matching happens in business validation.
    currency_valid = bool(
        re.fullmatch(r"[A-Z]{3}", normalized_currency)
    )

    if currency and not currency_valid:
        message = (
            f"Currency '{currency}' is not a valid three-letter "
            "currency code format."
        )
        errors.append(message)
        _add_discrepancy(
            discrepancies,
            discrepancy_type="invalid_currency_format",
            message=message,
            details={"value": str(currency)},
        )

    # -------------------------------------------------------------
    # Amount validation
    # -------------------------------------------------------------

    subtotal = _to_decimal(subtotal_value)
    tax_amount = _to_decimal(tax_value)
    tax_rate = _to_decimal(tax_rate_value)
    total_amount = _to_decimal(total_value)

    amount_values = {
        "subtotal_amount": (subtotal_value, subtotal),
        "tax_amount": (tax_value, tax_amount),
        "tax_rate": (tax_rate_value, tax_rate),
        "total_amount": (total_value, total_amount),
    }

    for field, (raw_value, parsed_value) in amount_values.items():
        if raw_value is not None and parsed_value is None:
            message = f"{field} '{raw_value}' is not a valid numeric value."
            errors.append(message)
            _add_discrepancy(
                discrepancies,
                discrepancy_type="invalid_numeric_value",
                message=message,
                details={"field": field, "value": str(raw_value)},
            )

    for field, value in (
        ("subtotal_amount", subtotal),
        ("tax_amount", tax_amount),
        ("total_amount", total_amount),
    ):
        if value is not None and value < 0:
            message = (
                f"{field} is negative ({value}). Verify whether this "
                "document is a credit note or debit note."
            )
            warnings.append(message)
            _add_discrepancy(
                discrepancies,
                discrepancy_type="negative_amount",
                message=message,
                severity="medium",
                details={"field": field, "value": str(value)},
            )

    if tax_rate is not None and not (Decimal("0") <= tax_rate <= Decimal("100")):
        message = f"Tax rate {tax_rate}% is outside the expected 0–100% range."
        errors.append(message)
        _add_discrepancy(
            discrepancies,
            discrepancy_type="invalid_tax_rate",
            message=message,
            details={"tax_rate": str(tax_rate)},
        )

    tolerance = _amount_tolerance()

    # -------------------------------------------------------------
    # Line-item validation
    # -------------------------------------------------------------

    normalized_line_items: list[dict[str, Any]] = []
    line_totals: list[Decimal] = []
    all_line_totals_present = bool(line_items)

    line_totals_valid = True

    if not isinstance(line_items, list):
        message = "Invoice line items must be a list."
        errors.append(message)
        _add_discrepancy(
            discrepancies,
            discrepancy_type="invalid_line_items",
            message=message,
        )
        line_items = []
        all_line_totals_present = False
        line_totals_valid = False

    for index, item in enumerate(line_items, start=1):
        if not isinstance(item, dict):
            message = f"Line item {index} is not a valid object."
            errors.append(message)
            _add_discrepancy(
                discrepancies,
                discrepancy_type="invalid_line_item",
                message=message,
                details={"line_number": index},
            )
            all_line_totals_present = False
            line_totals_valid = False
            continue

        normalized_item = dict(item)
        normalized_line_items.append(normalized_item)

        sku = (
            item.get("sku")
            or item.get("sku_code")
            or item.get("product_code")
            or item.get("item_code")
        )
        description = item.get("description")

        if not sku and not description:
            message = (
                f"Line item {index} has neither an item code nor a description."
            )
            errors.append(message)
            _add_discrepancy(
                discrepancies,
                discrepancy_type="missing_line_item_identity",
                message=message,
                details={"line_number": index},
            )

        quantity_raw = item.get("quantity")
        unit_price_raw = item.get("unit_price")
        line_total_raw = (
            item.get("line_total")
            if item.get("line_total") is not None
            else item.get("amount", item.get("total"))
        )

        quantity = _to_decimal(quantity_raw)
        unit_price = _to_decimal(unit_price_raw)
        line_total = _to_decimal(line_total_raw)

        if quantity_raw is not None and quantity is None:
            message = f"Line item {index} has an invalid quantity."
            errors.append(message)
            _add_discrepancy(
                discrepancies,
                discrepancy_type="invalid_line_quantity",
                message=message,
                details={"line_number": index, "value": str(quantity_raw)},
            )

        if unit_price_raw is not None and unit_price is None:
            message = f"Line item {index} has an invalid unit price."
            errors.append(message)
            _add_discrepancy(
                discrepancies,
                discrepancy_type="invalid_line_unit_price",
                message=message,
                details={"line_number": index, "value": str(unit_price_raw)},
            )

        if line_total_raw is not None and line_total is None:
            message = f"Line item {index} has an invalid line total."
            errors.append(message)
            _add_discrepancy(
                discrepancies,
                discrepancy_type="invalid_line_total",
                message=message,
                details={"line_number": index, "value": str(line_total_raw)},
            )

        if quantity is None or unit_price is None or line_total is None:
            all_line_totals_present = False

        if quantity is not None and quantity <= 0:
            message = f"Line item {index} quantity must be greater than zero."
            errors.append(message)
            _add_discrepancy(
                discrepancies,
                discrepancy_type="invalid_line_quantity",
                message=message,
                details={"line_number": index, "quantity": str(quantity)},
            )

        if unit_price is not None and unit_price < 0:
            message = f"Line item {index} has a negative unit price."
            warnings.append(message)
            _add_discrepancy(
                discrepancies,
                discrepancy_type="negative_line_unit_price",
                message=message,
                severity="medium",
                details={"line_number": index, "unit_price": str(unit_price)},
            )

        if line_total is not None:
            line_totals.append(line_total)

        if (
            quantity is not None
            and unit_price is not None
            and line_total is not None
        ):
            calculated = quantity * unit_price

            if abs(calculated - line_total) > tolerance:
                line_totals_valid = False
                message = (
                    f"Line item {index}: quantity × unit price "
                    f"({calculated}) does not match line total ({line_total})."
                )
                errors.append(message)
                _add_discrepancy(
                    discrepancies,
                    discrepancy_type="line_total_mismatch",
                    message=message,
                    details={
                        "line_number": index,
                        "quantity": str(quantity),
                        "unit_price": str(unit_price),
                        "calculated_total": str(calculated),
                        "line_total": str(line_total),
                    },
                )

    # Missing arithmetic values do not themselves prove a mismatch.
    # The completeness checks and human review flag handle those cases.
    if line_items and not all_line_totals_present:
        warnings.append(
            "Some line items are missing quantity, unit price, or line total; "
            "arithmetic validation is incomplete."
        )

    # -------------------------------------------------------------
    # Subtotal validation
    # -------------------------------------------------------------

    subtotal_valid = True

    if (
        normalized_line_items
        and all_line_totals_present
        and len(line_totals) == len(normalized_line_items)
        and subtotal is not None
    ):
        calculated_subtotal = sum(line_totals, Decimal("0"))

        if abs(calculated_subtotal - subtotal) > tolerance:
            subtotal_valid = False
            message = (
                f"Sum of line totals ({calculated_subtotal}) does not match "
                f"subtotal ({subtotal})."
            )
            errors.append(message)
            _add_discrepancy(
                discrepancies,
                discrepancy_type="subtotal_mismatch",
                message=message,
                details={
                    "calculated_subtotal": str(calculated_subtotal),
                    "subtotal": str(subtotal),
                },
            )
    elif subtotal is None:
        subtotal_valid = False
        warnings.append("Subtotal is unavailable; subtotal validation is incomplete.")

    # -------------------------------------------------------------
    # Tax validation
    # -------------------------------------------------------------

    tax_valid = True

    if subtotal is not None and tax_amount is not None and tax_rate is not None:
        expected_tax = subtotal * tax_rate / Decimal("100")

        if abs(expected_tax - tax_amount) > tolerance:
            tax_valid = False
            message = (
                f"Calculated tax ({expected_tax}) does not match extracted "
                f"tax amount ({tax_amount}) using tax rate {tax_rate}%."
            )
            warnings.append(message)
            _add_discrepancy(
                discrepancies,
                discrepancy_type="tax_calculation_mismatch",
                message=message,
                severity="medium",
                details={
                    "subtotal": str(subtotal),
                    "tax_rate_percent": str(tax_rate),
                    "calculated_tax": str(expected_tax),
                    "tax_amount": str(tax_amount),
                },
            )
    elif tax_amount is None:
        tax_valid = False
        warnings.append("Tax amount is unavailable; tax validation is incomplete.")

    # -------------------------------------------------------------
    # Total validation
    # -------------------------------------------------------------

    total_valid = True

    if subtotal is not None and tax_amount is not None and total_amount is not None:
        calculated_total = subtotal + tax_amount

        if abs(calculated_total - total_amount) > tolerance:
            total_valid = False
            message = (
                f"Subtotal plus tax ({calculated_total}) does not match "
                f"invoice total ({total_amount})."
            )
            errors.append(message)
            _add_discrepancy(
                discrepancies,
                discrepancy_type="invoice_total_mismatch",
                message=message,
                details={
                    "subtotal": str(subtotal),
                    "tax_amount": str(tax_amount),
                    "calculated_total": str(calculated_total),
                    "invoice_total": str(total_amount),
                },
            )
    else:
        total_valid = False
        warnings.append(
            "Subtotal, tax, or total is unavailable; total validation "
            "is incomplete."
        )

    # -------------------------------------------------------------
    # Final result
    # -------------------------------------------------------------

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

    existing_discrepancies = list(state.get("discrepancies") or [])

    # Avoid duplicating the same discrepancy when validation is rerun.
    # Keep previously resolved records intact; replace only currently
    # generated open discrepancies of the same type and message.
    generated_keys = {
        (item.get("type"), item.get("message"))
        for item in discrepancies
    }

    retained_discrepancies = [
        item
        for item in existing_discrepancies
        if (
            item.get("status") != "open"
            or (item.get("type"), item.get("message")) not in generated_keys
        )
    ]

    merged_discrepancies = retained_discrepancies + discrepancies

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
        "discrepancies": merged_discrepancies,
        "human_review_required": bool(
            state.get("human_review_required")
            or not data_validation_passed
        ),
        "processing_status": "data_validation_complete",
    }


# Compatibility alias for graphs that import validate_invoice.
def validate_invoice(state: dict[str, Any]) -> dict[str, Any]:
    return data_validate(state)
