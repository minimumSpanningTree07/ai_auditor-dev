from __future__ import annotations

from decimal import Decimal
from typing import Any

from agent.config import settings
from agent.services.erp_client import ERPClientError, erp_client


def _normalize(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip().lower()


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except Exception:
        return None


def _amount_equal(
    left: Any,
    right: Any,
) -> bool:
    left_decimal = _to_decimal(left)
    right_decimal = _to_decimal(right)

    if left_decimal is None or right_decimal is None:
        return False

    tolerance = Decimal(
        str(settings.amount_tolerance)
    )

    return abs(left_decimal - right_decimal) <= tolerance


def _get_po_line_items(
    purchase_order: dict[str, Any],
) -> list[dict[str, Any]]:
    items = purchase_order.get("line_items")

    if isinstance(items, list):
        return items

    return []


def _validate_line_items(
    invoice_items: list[dict[str, Any]],
    po_items: list[dict[str, Any]],
) -> tuple[
    bool,
    bool,
    bool,
    list[str],
]:
    errors: list[str] = []

    if not invoice_items:
        return (
            False,
            False,
            False,
            ["Invoice contains no line items."],
        )

    if not po_items:
        return (
            False,
            False,
            False,
            ["Purchase order contains no line items."],
        )

    sku_match = True
    quantity_match = True
    unit_price_match = True

    po_by_sku: dict[str, dict[str, Any]] = {}

    for item in po_items:
        sku = _normalize(
            item.get("sku")
            or item.get("sku_code")
            or item.get("product_code")
        )

        if sku:
            po_by_sku[sku] = item

    for invoice_item in invoice_items:

        sku = _normalize(
            invoice_item.get("sku")
            or invoice_item.get("sku_code")
            or invoice_item.get("product_code")
        )

        if not sku:
            description = _normalize(
                invoice_item.get("description")
            )

            matching_po_item = next(
                (
                    item
                    for item in po_items
                    if _normalize(
                        item.get("description")
                    ) == description
                    and description
                ),
                None,
            )

            if matching_po_item:
                sku = _normalize(
                    matching_po_item.get("sku")
                    or matching_po_item.get("sku_code")
                    or matching_po_item.get("product_code")
                )

        po_item = po_by_sku.get(sku)

        if po_item is None:
            sku_match = False

            errors.append(
                f"Invoice line SKU '{sku or 'unknown'}' "
                "was not found in the purchase order."
            )

            continue

        invoice_quantity = invoice_item.get(
            "quantity"
        )

        po_quantity = po_item.get(
            "quantity"
        )

        if not _amount_equal(
            invoice_quantity,
            po_quantity,
        ):
            quantity_match = False

            errors.append(
                f"Quantity mismatch for SKU '{sku}': "
                f"invoice={invoice_quantity}, "
                f"PO={po_quantity}."
            )

        invoice_price = (
            invoice_item.get("unit_price")
        )

        po_price = (
            po_item.get("unit_price")
            or po_item.get("price")
        )

        if not _amount_equal(
            invoice_price,
            po_price,
        ):
            unit_price_match = False

            errors.append(
                f"Unit price mismatch for SKU '{sku}': "
                f"invoice={invoice_price}, "
                f"PO={po_price}."
            )

    return (
        sku_match,
        quantity_match,
        unit_price_match,
        errors,
    )


def business_validate(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate invoice information against Mock ERP.

    ERP information is retrieved exclusively through ERPClient.
    """

    vendor_name = (
        state.get("effective_vendor_name")
        or state.get("extracted_vendor_name")
    )

    po_number = (
        state.get("effective_po_number")
        or state.get("extracted_po_number")
    )

    invoice_currency = (
        state.get("effective_currency")
        or state.get("extracted_currency")
    )

    invoice_items = (
        state.get("effective_line_items")
        or state.get("extracted_line_items")
        or state.get("line_items")
        or []
    )

    errors: list[str] = []
    warnings: list[str] = []

    vendor_match = False
    po_match = False
    currency_match = False
    sku_match = False
    quantity_match = False
    unit_price_match = False

    vendor = None
    purchase_order = None
    po_items: list[dict[str, Any]] = []

    # ------------------------------------------------------------
    # Vendor validation
    # ------------------------------------------------------------

    if not vendor_name:
        errors.append(
            "Vendor name is missing."
        )
    else:
        try:
            vendor = erp_client.find_vendor(
                vendor_name
            )
        except ERPClientError as exc:
            errors.append(
                f"ERP vendor lookup failed: {exc}"
            )

        if vendor is None:
            errors.append(
                f"Vendor '{vendor_name}' was not found in ERP."
            )
        else:
            erp_vendor_name = (
                vendor.get("vendor_name")
                or vendor.get("name")
            )

            vendor_match = (
                _normalize(vendor_name)
                == _normalize(erp_vendor_name)
            )

            if not vendor_match:
                errors.append(
                    f"Vendor mismatch: "
                    f"invoice='{vendor_name}', "
                    f"ERP='{erp_vendor_name}'."
                )

    # ------------------------------------------------------------
    # Purchase order validation
    # ------------------------------------------------------------

    if not po_number:
        errors.append(
            "Purchase order number is missing."
        )
    else:
        try:
            purchase_order = (
                erp_client.get_purchase_order(
                    po_number
                )
            )
        except ERPClientError as exc:
            errors.append(
                f"ERP purchase-order lookup failed: {exc}"
            )

        if purchase_order is None:
            errors.append(
                f"Purchase order '{po_number}' "
                "was not found in ERP."
            )
        else:
            erp_po_number = (
                purchase_order.get("po_number")
                or purchase_order.get("number")
                or purchase_order.get("id")
            )

            po_match = (
                _normalize(po_number)
                == _normalize(erp_po_number)
            )

            if not po_match:
                errors.append(
                    f"PO mismatch: "
                    f"invoice='{po_number}', "
                    f"ERP='{erp_po_number}'."
                )

            po_items = _get_po_line_items(
                purchase_order
            )

            erp_currency = (
                purchase_order.get("currency")
                or (
                    vendor or {}
                ).get("currency")
            )

            if invoice_currency and erp_currency:
                currency_match = (
                    _normalize(invoice_currency)
                    == _normalize(erp_currency)
                )

                if not currency_match:
                    errors.append(
                        f"Currency mismatch: "
                        f"invoice='{invoice_currency}', "
                        f"ERP='{erp_currency}'."
                    )
            else:
                warnings.append(
                    "Currency could not be fully validated "
                    "against ERP."
                )

    # ------------------------------------------------------------
    # Line-item validation
    # ------------------------------------------------------------

    if purchase_order is not None:
        (
            sku_match,
            quantity_match,
            unit_price_match,
            line_errors,
        ) = _validate_line_items(
            invoice_items,
            po_items,
        )

        errors.extend(line_errors)

    # ------------------------------------------------------------
    # Final business validation
    # ------------------------------------------------------------

    business_passed = (
        vendor_match
        and po_match
        and currency_match
        and sku_match
        and quantity_match
        and unit_price_match
        and not errors
    )

    if not vendor_match:
        warnings.append(
            "Vendor validation did not pass."
        )

    if not po_match:
        warnings.append(
            "Purchase-order validation did not pass."
        )

    return {
        "erp_vendor": vendor,
        "erp_purchase_order": purchase_order,
        "erp_line_items": po_items,
        "vendor_match": vendor_match,
        "po_match": po_match,
        "currency_match": currency_match,
        "sku_match": sku_match,
        "quantity_match": quantity_match,
        "unit_price_match": unit_price_match,
        "business_validation_passed": business_passed,
        "business_validation_errors": errors,
        "business_validation_warnings": warnings,
        "validation_errors": errors,
        "validation_warnings": warnings,
        "human_review_required": not business_passed,
        "processing_status": (
            "business_validation_complete"
        ),
    }