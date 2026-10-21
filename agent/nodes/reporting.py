
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
import json


# ---------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------

def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, set):
        return list(value)

    return str(value)


def _json_safe(value: Any) -> Any:
    """
    Return a JSON-compatible copy without modifying the original state.
    """
    return json.loads(json.dumps(value, default=_json_default))


def _effective(state: dict[str, Any], field: str) -> Any:
    """
    Prefer corrected effective values, then canonical fields, then
    immutable extracted values.
    """
    value = state.get(f"effective_{field}")
    if value is not None:
        return value

    value = state.get(field)
    if value is not None:
        return value

    return state.get(f"extracted_{field}")


def _unique_messages(*groups: Any) -> list[str]:
    messages: list[str] = []

    for group in groups:
        if not isinstance(group, list):
            continue

        for message in group:
            if message is None:
                continue

            text = str(message).strip()
            if text and text not in messages:
                messages.append(text)

    return messages


def _open_discrepancies(
    discrepancies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Return unresolved discrepancies while preserving the original
    discrepancy dictionaries.
    """
    result: list[dict[str, Any]] = []

    for discrepancy in discrepancies:
        if not isinstance(discrepancy, dict):
            continue

        status = str(discrepancy.get("status") or "open").lower()

        if status not in {"resolved", "closed", "dismissed"}:
            result.append(discrepancy)

    return result


# ---------------------------------------------------------------------
# Validation summary
# ---------------------------------------------------------------------

def _build_validation_summary(
    state: dict[str, Any],
) -> dict[str, Any]:
    data_passed = state.get("data_validation_passed")
    business_passed = state.get("business_validation_passed")

    return {
        "data_validation_passed": data_passed,
        "business_validation_passed": business_passed,
        "required_fields_valid": state.get("required_fields_valid"),
        "line_totals_valid": state.get("line_totals_valid"),
        "subtotal_valid": state.get("subtotal_valid"),
        "tax_valid": state.get("tax_valid"),
        "total_valid": state.get("total_valid"),
        "date_valid": state.get("date_valid"),
        "currency_valid": state.get("currency_valid"),
        "vendor_match": state.get("vendor_match"),
        "po_match": state.get("po_match"),
        "currency_match": state.get("currency_match"),
        "sku_match": state.get("sku_match"),
        "quantity_match": state.get("quantity_match"),
        "unit_price_match": state.get("unit_price_match"),
    }


# ---------------------------------------------------------------------
# Recommendation and status
# ---------------------------------------------------------------------

def _determine_outcome(
    state: dict[str, Any],
    open_discrepancies: list[dict[str, Any]],
) -> tuple[str, str, bool]:
    """
    Determine the final audit outcome from the current validation run.

    An explicit auditor approval is a recorded human override: it updates
    the workflow status to approved while leaving findings visible in the
    report. Without that explicit override, a corrected invoice is approved
    only when the current validation results pass. Do not use the sticky
    human_review_required flag from an earlier extraction as a permanent veto.
    """
    decision = str(state.get("human_decision") or "").strip().lower()

    if decision in {"reject", "rejected"}:
        return "rejected", "reject", False

    # Explicit auditor approval is a deliberate override and remains auditable.
    # Normal correction flow uses revalidation and therefore reaches this branch
    # only after the current checks have been recomputed.
    if decision in {"approve", "approved"}:
        return "approved", "approve", False

    data_passed = state.get("data_validation_passed") is True
    business_passed = state.get("business_validation_passed") is True

    lookup_failed = bool(state.get("erp_lookup_failed"))
    missing_erp_records = state.get("missing_erp_records") or []
    missing_fields = state.get("missing_fields") or []

    if lookup_failed or missing_erp_records:
        return "invalid_erp", "reject", False

    if (
        not data_passed
        or not business_passed
        or missing_fields
        or open_discrepancies
    ):
        return "manual_review", "manual_review", True

    if decision in {"approve", "approved"}:
        return "approved", "approve", False

    return "approved", "approve", False


# ---------------------------------------------------------------------
# Audit score
# ---------------------------------------------------------------------

def _calculate_audit_score(
    state: dict[str, Any],
    open_discrepancies: list[dict[str, Any]],
) -> float:
    """
    Calculate a transparent rule-based score.

    This is a workflow completeness score, not a statistical probability
    that an invoice is correct.
    """
    checks = [
        state.get("required_fields_valid"),
        state.get("line_totals_valid"),
        state.get("subtotal_valid"),
        state.get("tax_valid"),
        state.get("total_valid"),
        state.get("date_valid"),
        state.get("currency_valid"),
        state.get("vendor_match"),
        state.get("po_match"),
        state.get("currency_match"),
        state.get("sku_match"),
        state.get("quantity_match"),
        state.get("unit_price_match"),
    ]

    known_checks = [check for check in checks if isinstance(check, bool)]

    if not known_checks:
        score = 0.0
    else:
        score = 100.0 * sum(known_checks) / len(known_checks)

    if open_discrepancies:
        high_count = sum(
            1
            for item in open_discrepancies
            if str(item.get("severity", "")).lower() == "high"
        )

        medium_count = sum(
            1
            for item in open_discrepancies
            if str(item.get("severity", "")).lower() == "medium"
        )

        score -= min(40.0, high_count * 10.0)
        score -= min(20.0, medium_count * 5.0)

    return round(max(0.0, min(100.0, score)), 2)


# ---------------------------------------------------------------------
# Main reporting node
# ---------------------------------------------------------------------

def generate_report(state: dict[str, Any]) -> dict[str, Any]:
    """
    Build the final invoice audit report.

    Expected upstream nodes:
      - field extraction
      - data validation
      - business validation
      - optional human review and revalidation

    This node does not persist the report to the database or filesystem.
    The persistence node handles those operations.
    """
    discrepancies = [
        item
        for item in (state.get("discrepancies") or [])
        if isinstance(item, dict)
    ]

    unresolved = _open_discrepancies(discrepancies)

    data_errors = state.get("data_validation_errors") or []
    business_errors = state.get("business_validation_errors") or []

    validation_errors = _unique_messages(
        state.get("validation_errors"),
        data_errors,
        business_errors,
    )

    validation_warnings = _unique_messages(
        state.get("validation_warnings"),
        state.get("data_validation_warnings"),
        state.get("business_validation_warnings"),
        state.get("warnings"),
    )

    human_decision = str(state.get("human_decision") or "").strip().lower()
    if human_decision in {"approve", "approved"} and unresolved:
        validation_warnings.append(
            "An auditor explicitly approved this invoice while one or more findings remain unresolved. "
            "Review the findings and recorded human feedback before payment."
        )

    validation_status, recommendation, human_review_required = (
        _determine_outcome(state, unresolved)
    )

    audit_score = _calculate_audit_score(state, unresolved)

    line_items = _effective(state, "line_items") or []

    invoice = {
        "invoice_id": state.get("invoice_id"),
        "invoice_number": _effective(state, "invoice_number"),
        "vendor_name": _effective(state, "vendor_name"),
        "vendor_id": state.get("vendor_id"),
        "po_number": _effective(state, "po_number"),
        "invoice_date": _effective(state, "invoice_date"),
        "currency": _effective(state, "currency"),
        "subtotal_amount": _effective(state, "subtotal_amount"),
        "tax_amount": _effective(state, "tax_amount"),
        "tax_rate": _effective(state, "tax_rate"),
        "total_amount": _effective(state, "total_amount"),
        "line_items": line_items,
    }

    validation_summary = _build_validation_summary(state)

    human_review = {
        "required": human_review_required,
        "decision": state.get("human_decision"),
        "feedback": state.get("human_feedback") or [],
        "corrections": state.get("human_corrections") or {},
        "missing_fields": state.get("missing_fields") or [],
        "missing_erp_records": state.get("missing_erp_records") or [],
    }

    report = {
        "report_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "invoice_id": state.get("invoice_id"),
        "file_name": state.get("file_name"),
        "validation_status": validation_status,
        "recommendation": recommendation,
        "audit_score": audit_score,
        "invoice": invoice,
        "validation": validation_summary,
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
        "discrepancies": discrepancies,
        "unresolved_discrepancies": unresolved,
        "human_review": human_review,
        "extraction": {
            "method": state.get("extraction_method"),
            "confidence": state.get("extraction_confidence"),
            "source_language": state.get("source_language"),
            "translation_used": state.get("translation_used"),
            "translation_confidence": state.get("translation_confidence"),
        },
    }

    # Ensure callers receive a serializable structure, including
    # Decimal values and dates returned by extraction or validation.
    report = _json_safe(report)

    summary_parts = [
        f"Invoice {invoice.get('invoice_number') or '(number unavailable)'}",
        f"status: {validation_status}",
        f"recommendation: {recommendation}",
        f"audit score: {audit_score}/100",
    ]

    if unresolved:
        summary_parts.append(
            f"{len(unresolved)} unresolved discrepancy/discrepancies"
        )

    report_summary = "; ".join(summary_parts)

    return {
        "report": report,
        "report_summary": report_summary,
        "validation_status": validation_status,
        "recommendation": recommendation,
        "human_review_required": human_review_required,
        "audit_score": audit_score,
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
        "processing_status": "reporting_complete",
    }


# ---------------------------------------------------------------------
# Compatibility aliases
# ---------------------------------------------------------------------

def reporting_node(state: dict[str, Any]) -> dict[str, Any]:
    """Compatibility alias for graphs using reporting_node."""
    return generate_report(state)


def human_in_loop(state: dict[str, Any]) -> dict[str, Any]:
    """
    Compatibility fallback for older graphs.

    A real resumable human-in-the-loop workflow should use LangGraph's
    interrupt() with a configured checkpointer, as in the graph update.
    This function does not pretend to pause execution by itself.
    """
    if not state.get("human_review_required"):
        return {
            "processing_status": "human_review_not_required",
        }

    return {
        "human_review_required": True,
        "processing_status": "human_review_required",
        "warnings": _unique_messages(
            state.get("warnings"),
            [
                "Human review is required. Resume the checkpointed graph "
                "with a decision, feedback, or corrections."
            ],
        ),
    }
