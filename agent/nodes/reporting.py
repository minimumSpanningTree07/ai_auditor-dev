from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _status(
    business_passed: bool,
    data_passed: bool,
    human_review_required: bool,
) -> str:
    if human_review_required:
        return "manual_review"

    if business_passed and data_passed:
        return "approved"

    return "rejected"


def _recommendation(
    status: str,
    discrepancies: list[dict[str, Any]],
) -> str:
    if status == "approved":
        return "Invoice can proceed for processing."

    if status == "manual_review":
        if discrepancies:
            return (
                "Manual review is required to resolve "
                "the detected discrepancies."
            )

        return (
            "Manual review is required because the invoice "
            "could not be fully validated."
        )

    return (
        "Invoice should not proceed until validation "
        "failures are resolved."
    )


def generate_report(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a structured validation report.

    This node does not persist the report. Persistence is handled by
    the persistence node.
    """

    business_passed = bool(
        state.get(
            "business_validation_passed",
            False,
        )
    )

    data_passed = bool(
        state.get(
            "data_validation_passed",
            False,
        )
    )

    business_errors = list(
        state.get(
            "business_validation_errors"
        )
        or []
    )

    data_errors = list(
        state.get(
            "data_validation_errors"
        )
        or []
    )

    business_warnings = list(
        state.get(
            "business_validation_warnings"
        )
        or []
    )

    data_warnings = list(
        state.get(
            "data_validation_warnings"
        )
        or []
    )

    validation_errors = (
        business_errors
        + data_errors
    )

    validation_warnings = (
        business_warnings
        + data_warnings
    )

    discrepancies = list(
        state.get("discrepancies")
        or []
    )

    # Convert validation failures into structured discrepancies
    # when a previous node has not already created them.
    if not discrepancies:
        discrepancies = [
            {
                "type": "validation_error",
                "message": error,
                "severity": "high",
            }
            for error in validation_errors
        ]

    human_review_required = bool(
        state.get(
            "human_review_required",
            False,
        )
    ) or bool(discrepancies)

    validation_status = _status(
        business_passed,
        data_passed,
        human_review_required,
    )

    recommendation = _recommendation(
        validation_status,
        discrepancies,
    )

    invoice_number = (
        state.get("effective_invoice_number")
        or state.get("extracted_invoice_number")
    )

    report = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "invoice": {
            "invoice_id": state.get("invoice_id"),
            "invoice_number": invoice_number,
            "vendor_name": (
                state.get("effective_vendor_name")
                or state.get("extracted_vendor_name")
            ),
            "po_number": (
                state.get("effective_po_number")
                or state.get("extracted_po_number")
            ),
            "invoice_date": (
                state.get("effective_invoice_date")
                or state.get("extracted_invoice_date")
            ),
            "currency": (
                state.get("effective_currency")
                or state.get("extracted_currency")
            ),
            "subtotal_amount": (
                state.get("effective_subtotal_amount")
                if state.get("effective_subtotal_amount")
                is not None
                else state.get("extracted_subtotal_amount")
            ),
            "tax_amount": (
                state.get("effective_tax_amount")
                if state.get("effective_tax_amount")
                is not None
                else state.get("extracted_tax_amount")
            ),
            "tax_rate": (
                state.get("effective_tax_rate")
                if state.get("effective_tax_rate")
                is not None
                else state.get("extracted_tax_rate")
            ),
            "total_amount": (
                state.get("effective_total_amount")
                if state.get("effective_total_amount")
                is not None
                else state.get("extracted_total_amount")
            ),
        },

        "validation": {
            "status": validation_status,
            "business_validation_passed": business_passed,
            "data_validation_passed": data_passed,
            "required_fields_valid": state.get(
                "required_fields_valid",
                False,
            ),
            "line_totals_valid": state.get(
                "line_totals_valid",
                False,
            ),
            "subtotal_valid": state.get(
                "subtotal_valid",
                False,
            ),
            "tax_valid": state.get(
                "tax_valid",
                False,
            ),
            "total_valid": state.get(
                "total_valid",
                False,
            ),
            "date_valid": state.get(
                "date_valid",
                False,
            ),
            "currency_valid": state.get(
                "currency_valid",
                False,
            ),
        },

        "erp": {
            "vendor": state.get("erp_vendor"),
            "purchase_order": state.get(
                "erp_purchase_order"
            ),
            "line_items": state.get(
                "erp_line_items",
                [],
            ),
        },

        "discrepancies": discrepancies,

        "errors": validation_errors,

        "warnings": validation_warnings,

        "human_review": {
            "required": human_review_required,
            "decision": state.get(
                "human_decision"
            ),
            "feedback": state.get(
                "human_feedback"
            ),
            "corrections": state.get(
                "human_corrections",
                {},
            ),
        },

        "recommendation": recommendation,
    }

    summary = {
        "status": validation_status,
        "invoice_number": invoice_number,
        "discrepancy_count": len(
            discrepancies
        ),
        "error_count": len(
            validation_errors
        ),
        "warning_count": len(
            validation_warnings
        ),
        "human_review_required": human_review_required,
        "recommendation": recommendation,
    }

    return {
        "report": report,
        "report_summary": summary,
        "discrepancies": discrepancies,
        "validation_status": validation_status,
        "recommendation": recommendation,
        "human_review_required": human_review_required,
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
        "processing_status": "reporting_complete",
    }