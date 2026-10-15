
import logging
import os
from pathlib import Path
from typing import Any

import requests
import yaml

from agents.state import InvoiceState

logger = logging.getLogger(__name__)

MOCK_ERP_URL = os.getenv(
    "MOCK_ERP_URL",
    "http://mock-erp:8000",
)
TIMEOUT = 10

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = PROJECT_ROOT / "config" / "rules.yaml"


def load_rules() -> dict[str, Any]:
    with RULES_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}

def get_or_create_vendor(vendor_name: str) -> dict:
    vendor_name = vendor_name.strip()

    if not vendor_name:
        raise ValueError("Vendor name is missing")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Prevent concurrent vendor ID generation conflicts.
            cur.execute("SELECT pg_advisory_xact_lock(735219)")

            cur.execute(
                """
                SELECT vendor_id, vendor_name, country, currency
                FROM erp.vendors
                WHERE LOWER(TRIM(vendor_name)) = LOWER(TRIM(%s))
                LIMIT 1
                """,
                (vendor_name,),
            )
            vendor = cur.fetchone()

            if vendor:
                return dict(vendor)

            cur.execute(
                """
                SELECT COALESCE(
                    MAX(
                        CAST(
                            SUBSTRING(vendor_id FROM '^VEND-([0-9]+)$')
                            AS INTEGER
                        )
                    ), 0
                ) AS max_id
                FROM erp.vendors
                WHERE vendor_id ~ '^VEND-[0-9]+$'
                """
            )

            next_id = cur.fetchone()["max_id"] + 1
            vendor_id = f"VEND-{next_id:03d}"

            cur.execute(
                """
                INSERT INTO erp.vendors
                    (vendor_id, vendor_name, country, currency)
                VALUES (%s, %s, NULL, NULL)
                RETURNING vendor_id, vendor_name, country, currency
                """,
                (vendor_id, vendor_name),
            )

            return dict(cur.fetchone())


def get_erp_record(endpoint: str) -> dict[str, Any]:
    """Fetch ERP data through Mock ERP HTTP API."""
    url = f"{MOCK_ERP_URL.rstrip('/')}/{endpoint.lstrip('/')}"

    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected response from {url}")

    return data


def get_value(data: dict, *keys: str):
    for key in keys:
        if data.get(key) is not None:
            return data[key]
    return None


def as_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def record_discrepancy(
    discrepancies: list,
    field_name: str,
    invoice_value,
    erp_value,
    deviation_pct=None,
    severity="medium",
):
    discrepancies.append({
        "field_name": field_name,
        "invoice_value": (
            None if invoice_value is None else str(invoice_value)
        ),
        "erp_value": (
            None if erp_value is None else str(erp_value)
        ),
        "deviation_pct": deviation_pct,
        "severity": severity,
    })


def compare_numeric(
    discrepancies: list,
    field_name: str,
    invoice_value,
    erp_value,
    tolerance_pct: float,
):
    invoice_num = as_number(invoice_value)
    erp_num = as_number(erp_value)

    if invoice_num is None or erp_num is None:
        record_discrepancy(
            discrepancies,
            field_name,
            invoice_value,
            erp_value,
            severity="high",
        )
        return

    if erp_num == 0:
        deviation = 0.0 if invoice_num == 0 else None
    else:
        deviation = (
            abs(invoice_num - erp_num) / abs(erp_num)
        ) * 100

    if deviation is None or deviation > tolerance_pct:
        record_discrepancy(
            discrepancies,
            field_name,
            invoice_num,
            erp_num,
            deviation,
            severity="high" if deviation is None
            or deviation > tolerance_pct * 2
            else "medium",
        )


def get_po_lines(po: dict) -> list[dict]:
    """Support common names for PO line arrays."""
    lines = get_value(
        po, "line_items", "po_line_items", "items"
    )
    return lines if isinstance(lines, list) else []


def find_matching_po_line(
    po_lines: list[dict],
    item_code,
):
    for line in po_lines:
        po_code = get_value(
            line, "item_code", "sku_code", "sku"
        )
        if (
            item_code is not None
            and po_code is not None
            and str(item_code).strip().casefold()
            == str(po_code).strip().casefold()
        ):
            return line

    return None


def business_validation(state: InvoiceState) -> dict:
    """
    Compare invoice values with ERP records obtained through HTTP.
    Does not query PostgreSQL directly.
    """
    rules = load_rules()
    tolerances = rules.get("tolerances", {})

    price_tolerance = float(
        tolerances.get("price_difference_percent", 5)
    )
    quantity_tolerance = float(
        tolerances.get("quantity_difference_percent", 0)
    )

    po_number = state.get("po_number")
    lines = state.get("line_items") or []
    raw = state.get("extracted_raw") or {}
    vendor_name = state.get("vendor_name")
    discrepancies = list(state.get("discrepancies") or [])
    errors = list(state.get("validation_errors") or [])
    warnings = list(state.get("validation_warnings") or [])
    if not vendor_name:
        return {
            "validation_status": "failed",
            "validation_errors": ["Vendor name is missing"],
            "current_stage": "business_validation_failed",
        }

    erp_vendor = get_or_create_vendor(vendor_name)
    vendor_id = erp_vendor["vendor_id"]



    if not po_number:
        return {
            "validation_status": "failed",
            "validation_errors": errors + [
                "Missing purchase order number."
            ],
            "validation_warnings": warnings,
            "discrepancies": discrepancies,
            "current_stage": "business_validation_completed",
        }

    try:
        # All ERP records are obtained through Mock ERP HTTP endpoints.
        po = get_erp_record(f"/po/{po_number}")

        vendor = (
            get_erp_record(f"/vendor/{vendor_id}")
            if vendor_id else None
        )

        po_lines = get_po_lines(po)
        sku_records = {}

        # Compare each invoice line against its matching PO line.
        for index, invoice_line in enumerate(lines, start=1):
            item_code = get_value(
                invoice_line, "item_code", "sku_code", "sku"
            )

            if not item_code:
                record_discrepancy(
                    discrepancies,
                    f"line_{index}.item_code",
                    None,
                    None,
                    severity="high",
                )
                continue

            sku = get_erp_record(f"/sku/{item_code}")
            sku_records[str(item_code)] = sku

            po_line = find_matching_po_line(
                po_lines, item_code
            )

            if po_line is None:
                record_discrepancy(
                    discrepancies,
                    f"line_{index}.purchase_order_item",
                    item_code,
                    None,
                    severity="high",
                )
                continue

            # Quantity comparison
            compare_numeric(
                discrepancies,
                f"line_{index}.quantity",
                get_value(invoice_line, "quantity", "qty"),
                get_value(po_line, "quantity", "qty"),
                quantity_tolerance,
            )

            # Unit-price comparison
            compare_numeric(
                discrepancies,
                f"line_{index}.unit_price",
                get_value(invoice_line, "unit_price", "price"),
                get_value(po_line, "unit_price", "price"),
                price_tolerance,
            )

        # Currency comparison against the PO.
        invoice_currency = state.get("currency")
        po_currency = get_value(po, "currency", "currency_code")

        if (
            invoice_currency is not None
            and po_currency is not None
            and str(invoice_currency).strip().upper()
            != str(po_currency).strip().upper()
        ):
            record_discrepancy(
                discrepancies,
                "currency",
                invoice_currency,
                po_currency,
                severity="high",
            )

        # Vendor master comparison.
        if vendor:
            erp_vendor_id = get_value(vendor, "vendor_id", "id")

            if (
                erp_vendor_id is not None
                and vendor_id is not None
                and str(erp_vendor_id).casefold()
                != str(vendor_id).casefold()
            ):
                record_discrepancy(
                    discrepancies,
                    "vendor_id",
                    vendor_id,
                    erp_vendor_id,
                    severity="high",
                )

            invoice_vendor = state.get("vendor_name")
            erp_vendor_name = get_value(
                vendor, "vendor_name", "name"
            )

            if (
                invoice_vendor
                and erp_vendor_name
                and str(invoice_vendor).strip().casefold()
                != str(erp_vendor_name).strip().casefold()
            ):
                record_discrepancy(
                    discrepancies,
                    "vendor_name",
                    invoice_vendor,
                    erp_vendor_name,
                    severity="high",
                )

    except (requests.RequestException, ValueError) as exc:
        logger.exception("Business validation could not retrieve ERP data")
        errors.append(f"Mock ERP request/response error: {exc}")

        return {
            "validation_status": "failed",
            "validation_errors": errors,
            "validation_warnings": warnings,
            "discrepancies": discrepancies,
            "current_stage": "business_validation_completed",
        }

    validation_status = (
        "failed" if errors
        else "partial" if discrepancies
        else "passed"
    )

    return {
        "erp_purchase_order": po,
        "erp_vendor": vendor,
        "erp_sku_data":list(sku_records.values()),
        "discrepancies": discrepancies,
        "validation_errors": errors,
        "validation_warnings": warnings,
        "validation_status": validation_status,
        "current_stage": "business_validation_completed",
    }

