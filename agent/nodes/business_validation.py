
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from agent.config import settings
from agent.services.erp_client import ERPClientError, erp_client


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().casefold()


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None

    try:
        return Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _amount_equal(left: Any, right: Any) -> bool:
    left_decimal = _to_decimal(left)
    right_decimal = _to_decimal(right)

    if left_decimal is None or right_decimal is None:
        return False

    try:
        tolerance = Decimal(str(settings.amount_tolerance))
    except (AttributeError, InvalidOperation, TypeError, ValueError):
        tolerance = Decimal("0.02")

    return abs(left_decimal - right_decimal) <= tolerance


def _effective(state: dict[str, Any], field: str) -> Any:
    """
    Prefer human-corrected effective values, then canonical fields,
    then the original extracted values.
    """
    value = state.get(f"effective_{field}")
    if value is not None:
        return value

    value = state.get(field)
    if value is not None:
        return value

    return state.get(f"extracted_{field}")


def _get_po_line_items(
    purchase_order: dict[str, Any],
) -> list[dict[str, Any]]:
    items = purchase_order.get("line_items")

    if not isinstance(items, list):
        return []

    return [item for item in items if isinstance(item, dict)]


def _get_sku(item: dict[str, Any]) -> str:
    return _normalize(
        item.get("sku")
        or item.get("sku_code")
        or item.get("product_code")
        or item.get("item_code")
    )


def _get_invoice_line_items(
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Business validation must always use effective/human-corrected
    invoice values. Original extracted values are fallback only.
    """
    items = state.get("effective_line_items")

    if items is None:
        items = state.get("line_items")

    if items is None:
        items = state.get("extracted_line_items")

    if not isinstance(items, list):
        return []

    return [
        item
        for item in items
        if isinstance(item, dict)
    ]


def _add_discrepancy(
    discrepancies: list[dict[str, Any]],
    discrepancy_type: str,
    message: str,
    *,
    severity: str = "high",
    details: dict[str, Any] | None = None,
) -> None:
    discrepancies.append(
        {
            "type": discrepancy_type,
            "severity": severity,
            "message": message,
            "details": details or {},
            "status": "open",
        }
    )


def _validate_line_items(
    invoice_items: list[dict[str, Any]],
    po_items: list[dict[str, Any]],
) -> tuple[bool, bool, bool, list[str], list[dict[str, Any]]]:
    """
    Compare invoice line items with PO line items.

    A line can match by SKU or, when the invoice has no SKU, by an
    exact non-empty description. Quantities and prices are then checked
    against the matched PO line.
    """
    errors: list[str] = []
    discrepancies: list[dict[str, Any]] = []

    if not invoice_items:
        message = "Invoice contains no line items."
        return (
            False,
            False,
            False,
            [message],
            [{
                "type": "missing_invoice_line_items",
                "severity": "high",
                "message": message,
                "details": {},
                "status": "open",
            }],
        )

    if not po_items:
        message = "Purchase order contains no line items."
        return (
            False,
            False,
            False,
            [message],
            [{
                "type": "missing_po_line_items",
                "severity": "high",
                "message": message,
                "details": {},
                "status": "open",
            }],
        )

    sku_match = True
    quantity_match = True
    unit_price_match = True

    po_by_sku: dict[str, dict[str, Any]] = {}

    for po_item in po_items:
        sku = _get_sku(po_item)
        if sku:
            po_by_sku[sku] = po_item

    for index, invoice_item in enumerate(invoice_items, start=1):
        sku = _get_sku(invoice_item)
        po_item = po_by_sku.get(sku) if sku else None

        if po_item is None and not sku:
            description = _normalize(invoice_item.get("description"))

            if description:
                po_item = next(
                    (
                        item
                        for item in po_items
                        if _normalize(item.get("description")) == description
                    ),
                    None,
                )

                if po_item is not None:
                    sku = _get_sku(po_item)

        if po_item is None:
            sku_match = False
            message = (
                f"Invoice line {index} SKU "
                f"'{sku or 'unknown'}' was not found in the purchase order."
            )
            errors.append(message)
            discrepancies.append(
                {
                    "type": "po_sku_mismatch",
                    "severity": "high",
                    "message": message,
                    "details": {
                        "line_number": index,
                        "invoice_sku": sku or None,
                        "description": invoice_item.get("description"),
                    },
                    "status": "open",
                }
            )
            continue

        invoice_quantity = invoice_item.get("quantity")
        po_quantity = po_item.get("quantity")

        if not _amount_equal(invoice_quantity, po_quantity):
            quantity_match = False
            message = (
                f"Quantity mismatch for SKU '{sku or 'unknown'}': "
                f"invoice={invoice_quantity}, PO={po_quantity}."
            )
            errors.append(message)
            discrepancies.append(
                {
                    "type": "po_quantity_mismatch",
                    "severity": "high",
                    "message": message,
                    "details": {
                        "line_number": index,
                        "sku": sku or None,
                        "invoice_quantity": invoice_quantity,
                        "po_quantity": po_quantity,
                    },
                    "status": "open",
                }
            )

        invoice_price = invoice_item.get("unit_price")
        po_price = (
            po_item.get("unit_price")
            if po_item.get("unit_price") is not None
            else po_item.get("price")
        )

        if not _amount_equal(invoice_price, po_price):
            unit_price_match = False
            message = (
                f"Unit price mismatch for SKU '{sku or 'unknown'}': "
                f"invoice={invoice_price}, PO={po_price}."
            )
            errors.append(message)
            discrepancies.append(
                {
                    "type": "po_unit_price_mismatch",
                    "severity": "high",
                    "message": message,
                    "details": {
                        "line_number": index,
                        "sku": sku or None,
                        "invoice_unit_price": invoice_price,
                        "po_unit_price": po_price,
                    },
                    "status": "open",
                }
            )

    return sku_match, quantity_match, unit_price_match, errors, discrepancies


# ---------------------------------------------------------------------
# Business validation node
# ---------------------------------------------------------------------

def business_validate(state: dict[str, Any]) -> dict[str, Any]:
    """
    Validate invoice business data against Mock ERP.

    This node only reads ERP master data. It does not create or update
    ERP vendors, purchase orders, or SKUs.

    Missing ERP records are identified separately from lookup failures
    so the graph can route missing master data to an authorized user.
    """
    vendor_name = _effective(state, "vendor_name")
    vendor_id = state.get("vendor_id")
    po_number = _effective(state, "po_number")
    invoice_currency = _effective(state, "currency")
    invoice_items = _get_invoice_line_items(state)

    errors: list[str] = []
    warnings: list[str] = []
    discrepancies: list[dict[str, Any]] = []
    missing_erp_records: list[dict[str, Any]] = []

    vendor_match = False
    po_match = False
    currency_match = False
    sku_match = False
    quantity_match = False
    unit_price_match = False

    vendor: dict[str, Any] | None = None
    purchase_order: dict[str, Any] | None = None
    po_items: list[dict[str, Any]] = []
    erp_skus: list[dict[str, Any]] = []

    lookup_failed = False

    # -------------------------------------------------------------
    # Vendor lookup
    # -------------------------------------------------------------

    if not vendor_name and not vendor_id:
        message = "Vendor name or ERP vendor ID is missing."
        errors.append(message)
        _add_discrepancy(
            discrepancies,
            "missing_vendor_identity",
            message,
            details={"vendor_name": vendor_name, "vendor_id": vendor_id},
        )
    else:
        try:
            if vendor_id:
                vendor = erp_client.get_vendor(str(vendor_id))
            else:
                vendor = erp_client.find_vendor(str(vendor_name))

        except ERPClientError as exc:
            # The current ERP client returns an empty dictionary for
            # HTTP 404. Other client errors are treated as lookup errors.
            lookup_failed = True
            message = f"ERP vendor lookup failed: {exc}"
            errors.append(message)
            _add_discrepancy(
                discrepancies,
                "erp_vendor_lookup_failed",
                message,
                details={"vendor_id": vendor_id, "vendor_name": vendor_name},
            )

        if not vendor and not lookup_failed:
            message = (
                f"Vendor '{vendor_name or vendor_id}' was not found in ERP."
            )
            errors.append(message)
            missing_erp_records.append(
                {
                    "record_type": "vendor",
                    "vendor_name": vendor_name,
                    "vendor_id": vendor_id,
                    "message": message,
                }
            )
            _add_discrepancy(
                discrepancies,
                "missing_erp_vendor",
                message,
                details={
                    "vendor_name": vendor_name,
                    "vendor_id": vendor_id,
                },
            )

        if vendor:
            erp_vendor_name = (
                vendor.get("vendor_name")
                or vendor.get("name")
            )
            erp_vendor_id = vendor.get("vendor_id") or vendor.get("id")

            if vendor_name and erp_vendor_name:
                vendor_match = _normalize(vendor_name) == _normalize(
                    erp_vendor_name
                )
            elif vendor_id and erp_vendor_id:
                vendor_match = _normalize(vendor_id) == _normalize(
                    erp_vendor_id
                )
            else:
                vendor_match = bool(erp_vendor_id or erp_vendor_name)

            if not vendor_match:
                message = (
                    f"Vendor mismatch: invoice='{vendor_name or vendor_id}', "
                    f"ERP='{erp_vendor_name or erp_vendor_id}'."
                )
                errors.append(message)
                _add_discrepancy(
                    discrepancies,
                    "vendor_mismatch",
                    message,
                    details={
                        "invoice_vendor_name": vendor_name,
                        "invoice_vendor_id": vendor_id,
                        "erp_vendor_name": erp_vendor_name,
                        "erp_vendor_id": erp_vendor_id,
                    },
                )

    # -------------------------------------------------------------
    # Purchase-order lookup
    # -------------------------------------------------------------

    if not po_number:
        message = "Purchase order number is missing."
        errors.append(message)
        _add_discrepancy(
            discrepancies,
            "missing_purchase_order_number",
            message,
            details={},
        )
    else:
        try:
            purchase_order = erp_client.get_purchase_order(str(po_number))

        except ERPClientError as exc:
            lookup_failed = True
            message = f"ERP purchase-order lookup failed: {exc}"
            errors.append(message)
            _add_discrepancy(
                discrepancies,
                "erp_purchase_order_lookup_failed",
                message,
                details={"po_number": po_number},
            )

        if not purchase_order and not any(
            item.get("record_type") == "purchase_order"
            for item in missing_erp_records
        ) and not any(
            item.get("type") == "erp_purchase_order_lookup_failed"
            for item in discrepancies
        ):
            message = f"Purchase order '{po_number}' was not found in ERP."
            errors.append(message)
            missing_erp_records.append(
                {
                    "record_type": "purchase_order",
                    "po_number": po_number,
                    "message": message,
                }
            )
            _add_discrepancy(
                discrepancies,
                "missing_erp_purchase_order",
                message,
                details={"po_number": po_number},
            )

        if purchase_order:
            erp_po_number = (
                purchase_order.get("po_number")
                or purchase_order.get("number")
                or purchase_order.get("id")
            )

            po_match = _normalize(po_number) == _normalize(erp_po_number)

            if not po_match:
                message = (
                    f"PO mismatch: invoice='{po_number}', "
                    f"ERP='{erp_po_number}'."
                )
                errors.append(message)
                _add_discrepancy(
                    discrepancies,
                    "purchase_order_mismatch",
                    message,
                    details={
                        "invoice_po_number": po_number,
                        "erp_po_number": erp_po_number,
                    },
                )

            po_items = _get_po_line_items(purchase_order)

            # If the PO identifies its vendor, compare it to the invoice
            # vendor and to the retrieved vendor record when possible.
            po_vendor_id = (
                purchase_order.get("vendor_id")
                or purchase_order.get("vendor_code")
            )
            po_vendor_name = purchase_order.get("vendor_name")

            if po_vendor_id and vendor:
                erp_vendor_id = vendor.get("vendor_id") or vendor.get("id")
                if erp_vendor_id and _normalize(po_vendor_id) != _normalize(
                    erp_vendor_id
                ):
                    message = (
                        f"Purchase order '{po_number}' belongs to ERP vendor "
                        f"'{po_vendor_id}', not '{erp_vendor_id}'."
                    )
                    errors.append(message)
                    vendor_match = False
                    _add_discrepancy(
                        discrepancies,
                        "po_vendor_mismatch",
                        message,
                        details={
                            "po_vendor_id": po_vendor_id,
                            "invoice_vendor_id": erp_vendor_id,
                        },
                    )
            elif po_vendor_name and vendor_name:
                if _normalize(po_vendor_name) != _normalize(vendor_name):
                    message = (
                        f"Purchase order vendor '{po_vendor_name}' does not "
                        f"match invoice vendor '{vendor_name}'."
                    )
                    errors.append(message)
                    vendor_match = False
                    _add_discrepancy(
                        discrepancies,
                        "po_vendor_mismatch",
                        message,
                        details={
                            "po_vendor_name": po_vendor_name,
                            "invoice_vendor_name": vendor_name,
                        },
                    )

            erp_currency = (
                purchase_order.get("currency")
                or (vendor or {}).get("currency")
            )

            if invoice_currency and erp_currency:
                currency_match = (
                    _normalize(invoice_currency) == _normalize(erp_currency)
                )

                if not currency_match:
                    message = (
                        f"Currency mismatch: invoice='{invoice_currency}', "
                        f"ERP='{erp_currency}'."
                    )
                    errors.append(message)
                    _add_discrepancy(
                        discrepancies,
                        "currency_mismatch",
                        message,
                        details={
                            "invoice_currency": invoice_currency,
                            "erp_currency": erp_currency,
                        },
                    )
            else:
                message = (
                    "Currency could not be fully validated against ERP."
                )
                warnings.append(message)
                _add_discrepancy(
                    discrepancies,
                    "currency_not_fully_validated",
                    message,
                    severity="medium",
                    details={
                        "invoice_currency": invoice_currency,
                        "erp_currency": erp_currency,
                    },
                )

    # -------------------------------------------------------------
    # SKU master-data lookups
    # -------------------------------------------------------------

    # Check SKU master data only for invoice SKUs. The ERP client is the
    # sole integration boundary; no direct ERP database access is used.
    invoice_skus = list(
        dict.fromkeys(
            _get_sku(item)
            for item in invoice_items
            if _get_sku(item)
        )
    )

    for sku_code in invoice_skus:
        try:
            sku_record = erp_client.get_sku(sku_code)

        except ERPClientError as exc:
            lookup_failed = True
            message = f"ERP SKU lookup failed for '{sku_code}': {exc}"
            errors.append(message)
            _add_discrepancy(
                discrepancies,
                "erp_sku_lookup_failed",
                message,
                details={"sku": sku_code},
            )
            continue

        if not sku_record:
            message = f"SKU '{sku_code}' was not found in ERP master data."
            errors.append(message)
            missing_erp_records.append(
                {
                    "record_type": "sku",
                    "sku": sku_code,
                    "message": message,
                }
            )
            _add_discrepancy(
                discrepancies,
                "missing_erp_sku",
                message,
                details={"sku": sku_code},
            )
        else:
            erp_skus.append(sku_record)

    # -------------------------------------------------------------
    # PO line-item comparison
    # -------------------------------------------------------------

    if purchase_order:
        (
            sku_match,
            quantity_match,
            unit_price_match,
            line_errors,
            line_discrepancies,
        ) = _validate_line_items(invoice_items, po_items)

        errors.extend(line_errors)
        discrepancies.extend(line_discrepancies)

    # -------------------------------------------------------------
    # Final result
    # -------------------------------------------------------------

    # Avoid claiming successful validation when required comparisons
    # could not be completed.
    business_passed = (
        vendor_match
        and po_match
        and currency_match
        and sku_match
        and quantity_match
        and unit_price_match
        and not errors
        and not lookup_failed
        and not missing_erp_records
    )

    if not vendor_match:
        warnings.append("Vendor validation did not pass.")

    if not po_match:
        warnings.append("Purchase-order validation did not pass.")

    if missing_erp_records:
        warnings.append(
            "ERP master data is missing. An authorized user must resolve "
            "the missing records before final validation."
        )

    # -------------------------------------------------------------
    # Final discrepancy handling
    # -------------------------------------------------------------
    #
    # Revalidation always produces a fresh active discrepancy set.
    # Historical discrepancies remain preserved in the audit database
    # and must not be reused as active validation results.

    existing_discrepancies = list(state.get("discrepancies") or [])

    if state.get("workflow_mode") == "human_revalidation":
        # Revalidation starts a new validation pass. Preserve current data
        # validation findings and add current ERP findings, but never carry
        # forward open findings from the previous pass.
        current_data_findings = list(
            state.get("data_validation_discrepancies") or []
        )
        merged_discrepancies = current_data_findings + list(discrepancies)
    else:
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
        "erp_vendor": vendor,
        "erp_purchase_order": purchase_order,
        "erp_line_items": po_items,
        "erp_skus": erp_skus,
        "vendor_match": vendor_match,
        "po_match": po_match,
        "currency_match": currency_match,
        "sku_match": sku_match,
        "quantity_match": quantity_match,
        "unit_price_match": unit_price_match,
        "business_validation_passed": business_passed,
        "business_validation_errors": errors,
        "business_validation_warnings": warnings,
        "validation_errors": list(
            dict.fromkeys(
                list(state.get("data_validation_errors") or [])
                + errors
            )
        ),
        "validation_warnings": list(
            dict.fromkeys(
                list(state.get("data_validation_warnings") or [])
                + warnings
            )
        ),
        "missing_erp_records": missing_erp_records,
        "erp_lookup_failed": lookup_failed,
        "discrepancies": merged_discrepancies,
        "human_review_required": bool(
            state.get("human_review_required")
            or not business_passed
        ),
        "processing_status": "business_validation_complete",
    }


# Compatibility alias for callers using the older node name.
def business_validation(state: dict[str, Any]) -> dict[str, Any]:
    return business_validate(state)
