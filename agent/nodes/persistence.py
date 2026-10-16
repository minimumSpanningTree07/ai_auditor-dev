from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
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
    effective = state.get(
        f"effective_{field}"
    )

    if effective is not None:
        return effective

    return state.get(
        f"extracted_{field}"
    )


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

    reports_dir = Path(
        settings.reports_dir
    )

    reports_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = (
        reports_dir
        / f"{invoice_id}.json"
    )

    report_path.write_text(
        _json(report),
        encoding="utf-8",
    )

    return str(report_path)


def persist_invoice(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Persist the immutable extraction, effective values,
    validation results, discrepancies and audit information.

    The invoice binary itself remains on the filesystem.
    """

    invoice_id = _ensure_invoice_id(
        state
    )

    report = state.get("report")

    try:
        report_path = _save_report(
            invoice_id,
            report,
        )

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
        # Invoice master record
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
                %s, %s, %s, %s, %s,
                %s
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
                state.get(
                    "raw_extracted_text"
                ),
                state.get(
                    "translated_text"
                ),
                state.get(
                    "source_language"
                ),
                state.get(
                    "extraction_method"
                ),
                state.get(
                    "extraction_confidence"
                ),
                state.get(
                    "translation_used",
                    False,
                ),
                state.get(
                    "translation_confidence"
                ),
                state.get(
                    "validation_status"
                ),
                state.get(
                    "recommendation"
                ),
                state.get(
                    "human_review_required",
                    False,
                ),
                report_path,
            ],
        )

        # --------------------------------------------------------
        # Immutable original extraction
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
                state.get(
                    "extracted_invoice_number"
                ),
                state.get(
                    "extracted_vendor_name"
                ),
                state.get(
                    "extracted_po_number"
                ),
                state.get(
                    "extracted_invoice_date"
                ),
                state.get(
                    "extracted_currency"
                ),
                state.get(
                    "extracted_subtotal_amount"
                ),
                state.get(
                    "extracted_tax_amount"
                ),
                state.get(
                    "extracted_tax_rate"
                ),
                state.get(
                    "extracted_total_amount"
                ),
                _json(
                    state.get(
                        "extracted_line_items",
                        [],
                    )
                ),
                state.get(
                    "raw_extracted_text"
                ),
                state.get(
                    "extraction_method"
                ),
                state.get(
                    "extraction_confidence"
                ),
            ],
        )

        # --------------------------------------------------------
        # Effective line items
        # --------------------------------------------------------

        line_items = (
            state.get(
                "effective_line_items"
            )
            or state.get(
                "extracted_line_items"
            )
            or []
        )

        line_query = """
            DELETE FROM audit.invoice_line_items
            WHERE invoice_id = %s
        """

        db.execute(
            line_query,
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
                    item.get("sku"),
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

        discrepancy_query = """
            DELETE FROM audit.discrepancies
            WHERE invoice_id = %s
        """

        db.execute(
            discrepancy_query,
            [invoice_id],
        )

        discrepancies = state.get(
            "discrepancies"
        ) or []

        insert_discrepancy_query = """
            INSERT INTO audit.discrepancies (
                invoice_id,
                discrepancy_type,
                severity,
                message,
                details,
                status
            )
            VALUES (
                %s, %s, %s,
                %s, %s::jsonb, %s
            )
        """

        discrepancy_parameters = []

        for discrepancy in discrepancies:
            discrepancy_parameters.append(
                [
                    invoice_id,
                    discrepancy.get(
                        "type",
                        "validation_error",
                    ),
                    discrepancy.get(
                        "severity",
                        "high",
                    ),
                    discrepancy.get(
                        "message",
                        str(discrepancy),
                    ),
                    _json(discrepancy),
                    discrepancy.get(
                        "status",
                        "open",
                    ),
                ]
            )

        if discrepancy_parameters:
            db.execute_many(
                insert_discrepancy_query,
                discrepancy_parameters,
            )

        # --------------------------------------------------------
        # Human feedback
        # --------------------------------------------------------

        feedback = state.get(
            "human_feedback"
        )

        corrections = state.get(
            "human_corrections"
        ) or {}

        human_decision = state.get(
            "human_decision"
        )

        if feedback or corrections or human_decision:
            feedback_query = """
                INSERT INTO audit.human_feedback (
                    invoice_id,
                    decision,
                    feedback,
                    corrections
                )
                VALUES (
                    %s, %s, %s, %s::jsonb
                )
            """

            db.execute(
                feedback_query,
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

        audit_query = """
            INSERT INTO audit.audit_events (
                invoice_id,
                event_type,
                status,
                payload
            )
            VALUES (
                %s, %s, %s, %s::jsonb
            )
        """

        db.execute(
            audit_query,
            [
                invoice_id,
                "invoice_processing",
                state.get(
                    "validation_status"
                ),
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