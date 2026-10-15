
import json
import os

import psycopg
from psycopg.rows import dict_row


def get_connection():
    return psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
    )


def save_audit_report(
    state: dict,
    report: dict,
    missing_fields: list[str],
) -> None:
    """Persist the completed invoice audit in one transaction."""

    invoice_id = state["invoice_id"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Save the invoice header and final report.
            cur.execute(
                """
                INSERT INTO audit.invoice_audit (
                    invoice_id,
                    file_path,
                    file_checksum,
                    extraction_method,
                    raw_extracted_text,
                    translated_text,
                    source_language,
                    translation_confidence,
                    invoice_number,
                    vendor_name,
                    po_number,
                    invoice_date,
                    currency,
                    total_amount,
                    validation_status,
                    recommendation,
                    extracted_raw,
                    thread_id,
                    report_json,
                    report_summary,
                    missing_fields,
                    report_path
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb,
                    %s, %s::jsonb, %s
                )
                ON CONFLICT (invoice_id) DO UPDATE SET
                    file_path = EXCLUDED.file_path,
                    file_checksum = EXCLUDED.file_checksum,
                    extraction_method = EXCLUDED.extraction_method,
                    raw_extracted_text = EXCLUDED.raw_extracted_text,
                    translated_text = EXCLUDED.translated_text,
                    source_language = EXCLUDED.source_language,
                    translation_confidence = EXCLUDED.translation_confidence,
                    invoice_number = EXCLUDED.invoice_number,
                    vendor_name = EXCLUDED.vendor_name,
                    po_number = EXCLUDED.po_number,
                    invoice_date = EXCLUDED.invoice_date,
                    currency = EXCLUDED.currency,
                    total_amount = EXCLUDED.total_amount,
                    validation_status = EXCLUDED.validation_status,
                    recommendation = EXCLUDED.recommendation,
                    extracted_raw = EXCLUDED.extracted_raw,
                    thread_id = EXCLUDED.thread_id,
                    report_json = EXCLUDED.report_json,
                    report_summary = EXCLUDED.report_summary,
                    missing_fields = EXCLUDED.missing_fields,
                    report_path = EXCLUDED.report_path,
                    processed_at = now()
                """,
                (
                    invoice_id,
                    state.get("file_path"),
                    state.get("file_checksum"),
                    state.get("extraction_method"),
                    state.get("raw_extracted_text"),
                    state.get("translated_text"),
                    state.get("source_language"),
                    state.get("translation_confidence"),
                    state.get("invoice_number"),
                    state.get("vendor_name"),
                    state.get("po_number"),
                    state.get("invoice_date"),
                    state.get("currency"),
                    state.get("total_amount"),
                    state.get("validation_status"),
                    state.get("recommendation"),
                    json.dumps(state.get("extracted_raw") or {}, default=str),
                    state.get("thread_id"),
                    json.dumps(report, ensure_ascii=False, default=str),
                    report.get("summary"),
                    json.dumps(missing_fields),
                    report.get("report_path"),
                ),
            )

            # 2. Replace line items for this invoice.
            cur.execute(
                """
                DELETE FROM audit.invoice_line_items
                WHERE invoice_id = %s
                """,
                (invoice_id,),
            )

            for index, item in enumerate(
                state.get("line_items") or [], start=1
            ):
                cur.execute(
                    """
                    INSERT INTO audit.invoice_line_items (
                        invoice_id,
                        line_number,
                        item_code,
                        description,
                        quantity,
                        unit_price,
                        line_total
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        invoice_id,
                        item.get("line_number", index),
                        item.get("item_code"),
                        item.get("description"),
                        item.get("quantity"),
                        item.get("unit_price"),
                        item.get("line_total"),
                    ),
                )

            # 3. Replace discrepancies for this invoice.
            cur.execute(
                """
                DELETE FROM audit.discrepancies
                WHERE invoice_id = %s
                """,
                (invoice_id,),
            )

            for discrepancy in state.get("discrepancies") or []:
                cur.execute(
                    """
                    INSERT INTO audit.discrepancies (
                        invoice_id,
                        field_name,
                        invoice_value,
                        erp_value,
                        deviation_pct,
                        severity
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        invoice_id,
                        discrepancy.get("field_name", "unknown"),
                        (
                            str(discrepancy["invoice_value"])
                            if discrepancy.get("invoice_value") is not None
                            else None
                        ),
                        (
                            str(discrepancy["erp_value"])
                            if discrepancy.get("erp_value") is not None
                            else None
                        ),
                        discrepancy.get("deviation_pct"),
                        discrepancy.get("severity", "medium"),
                    ),
                )

        # psycopg commits when the connection context exits normally.
        # Exceptions trigger rollback.

