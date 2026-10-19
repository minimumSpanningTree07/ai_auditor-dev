from __future__ import annotations

import copy
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from agent.config import settings
from agent.services.database import DatabaseErrorHandler, db


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, Path):
        return str(value)

    return str(value)


def _json(value: Any) -> str:
    return json.dumps(
        value,
        default=_json_default,
    )


def _effective(
    state: dict[str, Any],
    field: str,
) -> Any:
    value = state.get(f"effective_{field}")

    if value is not None:
        return value

    return state.get(f"extracted_{field}")


def _ensure_invoice_id(
    state: dict[str, Any],
) -> str:
    invoice_id = state.get("invoice_id")

    if invoice_id:
        return str(invoice_id)

    import uuid

    return str(uuid.uuid4())


def _save_report(
    invoice_id: str,
    report: dict[str, Any] | None,
) -> str | None:
    if not report:
        return None

    reports_dir = Path(settings.reports_dir)

    reports_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = reports_dir / f"{invoice_id}.json"

    report_path.write_text(
        _json(report),
        encoding="utf-8",
    )

    return str(report_path)


def _normalize_sku(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip().lower()


def _build_effective_line_items(
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Build the effective line items.

    Priority:
        1. effective_line_items already produced by field extraction
        2. extracted_line_items + human corrections
        3. extracted_line_items

    The original extracted values are NEVER modified.
    """

    effective = state.get("effective_line_items")

    if effective:
        return copy.deepcopy(effective)

    original = state.get("extracted_line_items") or []

    line_items = copy.deepcopy(original)

    corrections = state.get("human_corrections") or {}
    correction_items = corrections.get("line_items") or []

    if not correction_items:
        return line_items

    for correction in correction_items:
        if not isinstance(correction, dict):
            continue

        correction_sku = (
            correction.get("sku")
            or correction.get("item_code")
            or correction.get("sku_code")
            or correction.get("product_code")
        )

        correction_sku_normalized = _normalize_sku(
            correction_sku
        )

        target = None

        # Match by SKU first.
        if correction_sku_normalized:
            for item in line_items:
                item_sku = (
                    item.get("sku")
                    or item.get("item_code")
                    or item.get("sku_code")
                    or item.get("product_code")
                )

                if (
                    _normalize_sku(item_sku)
                    == correction_sku_normalized
                ):
                    target = item
                    break

        # Fall back to line number.
        if target is None:
            line_number = correction.get("line_number")

            if line_number is not None:
                try:
                    index = int(line_number) - 1

                    if 0 <= index < len(line_items):
                        target = line_items[index]

                except (TypeError, ValueError):
                    pass

        if target is None:
            continue

        # Apply only explicitly supplied corrections.
        for field in (
            "sku",
            "item_code",
            "sku_code",
            "product_code",
            "description",
            "quantity",
            "unit_price",
            "line_total",
            "amount",
            "total",
            "unit_of_measure",
            "currency",
        ):
            if field in correction:
                target[field] = correction[field]

        # Keep SKU aliases synchronized.
        sku = (
            target.get("sku")
            or target.get("item_code")
            or target.get("sku_code")
            or target.get("product_code")
        )

        if sku:
            target["sku"] = sku
            target["item_code"] = sku
            target["sku_code"] = sku
            target["product_code"] = sku

        # Recalculate line total when quantity and unit price exist.
        quantity = target.get("quantity")
        unit_price = target.get("unit_price")

        try:
            if quantity is not None and unit_price is not None:
                target["line_total"] = str(
                    Decimal(str(quantity))
                    * Decimal(str(unit_price))
                )
        except (InvalidOperation, TypeError, ValueError):
            pass

    return line_items


def _persist_invoice_impl(
    state: dict[str, Any],
) -> dict[str, Any]:

    invoice_id = _ensure_invoice_id(state)

    report = state.get("report")

    try:
        report_path = _save_report(
            invoice_id,
            report,
        )

        # --------------------------------------------------------
        # Effective scalar values
        # --------------------------------------------------------

        invoice_number = _effective(
            state,
            "invoice_number",
        )

        vendor_name = _effective(
            state,
            "vendor_name",
        )

        po_number = _effective(
            state,
            "po_number",
        )

        invoice_date = _effective(
            state,
            "invoice_date",
        )

        currency = _effective(
            state,
            "currency",
        )

        subtotal_amount = _effective(
            state,
            "subtotal_amount",
        )

        tax_amount = _effective(
            state,
            "tax_amount",
        )

        tax_rate = _effective(
            state,
            "tax_rate",
        )

        total_amount = _effective(
            state,
            "total_amount",
        )

        # --------------------------------------------------------
        # Invoice master
        # --------------------------------------------------------

        invoice_query = """
            INSERT INTO audit.invoices (
                invoice_id,
                file_name,
                file_path,
                file_checksum,
                file_size,
                invoice_number,
                vendor_name,
                po_number,
                invoice_date,
                currency,
                subtotal_amount,
                tax_amount,
                tax_rate,
                total_amount,
                raw_extracted_text,
                translated_text,
                source_language,
                extraction_method,
                extraction_confidence,
                translation_used,
                translation_confidence,
                validation_status,
                recommendation,
                human_review_required,
                report_path
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (invoice_id)
            DO UPDATE SET
                file_name = EXCLUDED.file_name,
                file_path = EXCLUDED.file_path,
                file_checksum = EXCLUDED.file_checksum,
                file_size = EXCLUDED.file_size,
                invoice_number = EXCLUDED.invoice_number,
                vendor_name = EXCLUDED.vendor_name,
                po_number = EXCLUDED.po_number,
                invoice_date = EXCLUDED.invoice_date,
                currency = EXCLUDED.currency,
                subtotal_amount = EXCLUDED.subtotal_amount,
                tax_amount = EXCLUDED.tax_amount,
                tax_rate = EXCLUDED.tax_rate,
                total_amount = EXCLUDED.total_amount,
                raw_extracted_text = EXCLUDED.raw_extracted_text,
                translated_text = EXCLUDED.translated_text,
                source_language = EXCLUDED.source_language,
                extraction_method = EXCLUDED.extraction_method,
                extraction_confidence = EXCLUDED.extraction_confidence,
                translation_used = EXCLUDED.translation_used,
                translation_confidence = EXCLUDED.translation_confidence,
                validation_status = EXCLUDED.validation_status,
                recommendation = EXCLUDED.recommendation,
                human_review_required = EXCLUDED.human_review_required,
                report_path = EXCLUDED.report_path,
                updated_at = CURRENT_TIMESTAMP
            RETURNING invoice_id
        """

        db.insert_returning(
            invoice_query,
            [
                invoice_id,
                state.get("file_name"),
                state.get("file_path"),
                state.get("file_checksum"),
                state.get("file_size"),
                invoice_number,
                vendor_name,
                po_number,
                invoice_date,
                currency,
                subtotal_amount,
                tax_amount,
                tax_rate,
                total_amount,
                state.get("raw_extracted_text"),
                state.get("translated_text"),
                state.get("source_language"),
                state.get("extraction_method"),
                state.get("extraction_confidence"),
                state.get("translation_used", False),
                state.get("translation_confidence"),
                state.get("validation_status"),
                state.get("recommendation"),
                state.get("human_review_required", False),
                report_path,
            ],
        )

        # --------------------------------------------------------
        # IMMUTABLE ORIGINAL EXTRACTION
        # --------------------------------------------------------

        extraction_query = """
            INSERT INTO audit.invoice_extractions (
                invoice_id,
                extracted_invoice_number,
                extracted_vendor_name,
                extracted_po_number,
                extracted_invoice_date,
                extracted_currency,
                extracted_subtotal_amount,
                extracted_tax_amount,
                extracted_tax_rate,
                extracted_total_amount,
                extracted_line_items,
                raw_text,
                extraction_method,
                extraction_confidence
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s::jsonb, %s, %s, %s
            )
            ON CONFLICT (invoice_id)
            DO NOTHING
        """

        db.execute(
            extraction_query,
            [
                invoice_id,
                state.get("extracted_invoice_number"),
                state.get("extracted_vendor_name"),
                state.get("extracted_po_number"),
                state.get("extracted_invoice_date"),
                state.get("extracted_currency"),
                state.get("extracted_subtotal_amount"),
                state.get("extracted_tax_amount"),
                state.get("extracted_tax_rate"),
                state.get("extracted_total_amount"),
                _json(
                    state.get(
                        "extracted_line_items",
                        [],
                    )
                ),
                state.get("raw_extracted_text"),
                state.get("extraction_method"),
                state.get("extraction_confidence"),
            ],
        )

        # --------------------------------------------------------
        # EFFECTIVE LINE ITEMS
        # --------------------------------------------------------

        line_items = _build_effective_line_items(state)

        db.execute(
            """
            DELETE FROM audit.invoice_line_items
            WHERE invoice_id = %s
            """,
            [invoice_id],
        )

        insert_line_query = """
            INSERT INTO audit.invoice_line_items (
                invoice_id,
                line_number,
                sku,
                description,
                quantity,
                unit_price,
                line_total,
                source
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """

        line_parameters = []

        for index, item in enumerate(
            line_items,
            start=1,
        ):
            line_parameters.append(
                [
                    invoice_id,
                    index,
                    item.get("sku")
                    or item.get("item_code")
                    or item.get("sku_code")
                    or item.get("product_code"),
                    item.get("description"),
                    item.get("quantity"),
                    item.get("unit_price"),
                    (
                        item.get("line_total")
                        or item.get("amount")
                        or item.get("total")
                    ),
                    "effective",
                ]
            )

        if line_parameters:
            db.execute_many(
                insert_line_query,
                line_parameters,
            )

        # --------------------------------------------------------
        # Discrepancies
        # --------------------------------------------------------

        discrepancies = state.get("discrepancies") or []

        # Keep discrepancy IDs/history stable across revalidation. First mark
        # the currently-open findings resolved, then reactivate/update matching
        # findings from this validation pass. Findings still present remain open;
        # findings no longer produced by validation stay in history as resolved.
        existing_open = db.fetch_all(
            "SELECT id, discrepancy_type, message FROM audit.discrepancies WHERE invoice_id = %s AND UPPER(status) = 'OPEN' ORDER BY id",
            [invoice_id],
        )
        db.execute(
            "UPDATE audit.discrepancies SET status = 'resolved' WHERE invoice_id = %s AND UPPER(status) = 'OPEN'",
            [invoice_id],
        )

        unmatched_existing = list(existing_open)
        for discrepancy in discrepancies:
            dtype = str(discrepancy.get("type") or "validation_error")
            message = str(discrepancy.get("message") or discrepancy)
            match = next((row for row in unmatched_existing
                          if str(row.get("discrepancy_type")) == dtype
                          and str(row.get("message")) == message), None)
            severity = str(discrepancy.get("severity") or "high")
            details = _json(discrepancy)
            status = str(discrepancy.get("status") or "open").lower()
            if match:
                unmatched_existing.remove(match)
                db.execute(
                    "UPDATE audit.discrepancies SET severity = %s, details = %s::jsonb, status = %s WHERE id = %s",
                    [severity, details, status, match["id"]],
                )
            else:
                db.execute(
                    """INSERT INTO audit.discrepancies
                       (invoice_id, discrepancy_type, severity, message, details, status)
                       VALUES (%s, %s, %s, %s, %s::jsonb, %s)""",
                    [invoice_id, dtype, severity, message, details, status],
                )

        # --------------------------------------------------------
        # Human feedback
        # --------------------------------------------------------

        feedback = state.get("human_feedback")
        corrections = state.get(
            "human_corrections"
        ) or {}
        human_decision = state.get(
            "human_decision"
        )

        if feedback or corrections or human_decision:
            db.execute(
                """
                INSERT INTO audit.human_feedback (
                    invoice_id,
                    decision,
                    feedback,
                    corrections
                )
                VALUES (
                    %s, %s, %s, %s::jsonb
                )
                """,
                [
                    invoice_id,
                    human_decision,
                    feedback,
                    _json(corrections),
                ],
            )

        # --------------------------------------------------------
        # Audit event
        # --------------------------------------------------------

        db.execute(
            """
            INSERT INTO audit.audit_events (
                invoice_id,
                event_type,
                status,
                payload
            )
            VALUES (
                %s, %s, %s, %s::jsonb
            )
            """,
            [
                invoice_id,
                "invoice_processing",
                state.get("validation_status"),
                _json(
                    {
                        "business_validation_passed":
                            state.get(
                                "business_validation_passed"
                            ),
                        "data_validation_passed":
                            state.get(
                                "data_validation_passed"
                            ),
                        "human_review_required":
                            state.get(
                                "human_review_required"
                            ),
                        "report_path": report_path,
                    }
                ),
            ],
        )

        return {
            "invoice_id": invoice_id,
            "report_path": report_path,
            "persistence_status": "persisted",
            "persistence_error": None,
            "processing_status": "persistence_complete",
        }

    except DatabaseErrorHandler as exc:
        return {
            "invoice_id": invoice_id,
            "persistence_status": "failed",
            "persistence_error": str(exc),
            "processing_status": "failed",
            "errors": [
                f"Invoice persistence failed: {exc}"
            ],
        }

    except Exception as exc:
        return {
            "invoice_id": invoice_id,
            "persistence_status": "failed",
            "persistence_error": str(exc),
            "processing_status": "failed",
            "errors": [
                f"Invoice persistence failed: {exc}"
            ],
        }

class _PersistenceRollback(Exception):
    def __init__(self, result: dict[str, Any]):
        self.result = result
        super().__init__(str(result.get("persistence_error") or "Persistence failed"))


def persist_invoice(state: dict[str, Any]) -> dict[str, Any]:
    """Persist the full invoice snapshot atomically.

    All existing db.execute calls inside the implementation share this outer
    transaction. A failed operation forces rollback rather than committing a
    partially-updated invoice, line-item set, discrepancy set or audit history.
    """
    try:
        with db.transaction():
            result = _persist_invoice_impl(state)
            if result.get("persistence_status") != "persisted":
                raise _PersistenceRollback(result)
            return result
    except _PersistenceRollback as exc:
        return exc.result
    except Exception as exc:
        invoice_id = str(state.get("invoice_id") or "")
        return {
            "invoice_id": invoice_id,
            "persistence_status": "failed",
            "persistence_error": str(exc),
            "processing_status": "failed",
            "errors": [f"Invoice persistence transaction rolled back: {exc}"],
        }
