
import html
import json
from pathlib import Path

import yaml

from agents.state import InvoiceState
from agents.nodes.repository import save_audit_report


PROJECT_DIR = Path(__file__).resolve().parent.parent
RULES_PATH = PROJECT_DIR / "config" / "rules.yaml"
REPORT_DIR = PROJECT_DIR / "outputs" / "reports"


def load_rules():
    with RULES_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def find_missing_fields(state, rules):
    """Find missing required invoice aheader and line-item fields."""

    missing = []

    header_mapping = {
        "invoice_no": "invoice_number",
        "invoice_date": "invoice_date",
        "vendor_id": "vendor_id",
        "currency": "currency",
        "total_amount": "total_amount",
    }

    erp_vendor = state.get("erp_vendor") or {}

    for field in rules["required_fields"]["header"]:
        if field == "vendor_id":
            value = erp_vendor.get("vendor_id")
        else:
            value = state.get(header_mapping[field])

        if value is None or str(value).strip() == "":
            missing.append(field)

    line_items = state.get("line_items") or []

    if not line_items:
        missing.append("line_items")

    item_mapping = {
        "item_code": "item_code",
        "description": "description",
        "qty": "quantity",
        "unit_price": "unit_price",
        "total": "line_total",
    }

    for index, item in enumerate(line_items, start=1):
        for field in rules["required_fields"]["line_item"]:
            value = item.get(item_mapping[field])

            if value is None or str(value).strip() == "":
                missing.append(f"line_items[{index}].{field}")

    return missing


def determine_recommendation(state, missing_fields, rules):
    """Choose approve, manual_review, or reject."""

    currency = state.get("currency")
    accepted = rules.get("accepted_currencies", [])

    if currency and currency not in accepted:
        return "reject"

    if state.get("validation_status") == "failed":
        return "reject"

    if (
        missing_fields
        or state.get("validation_errors")
        or state.get("validation_warnings")
        or state.get("discrepancies")
    ):
        return "manual_review"

    confidence = state.get("translation_confidence")
    threshold = rules["validation_policies"].get(
        "auto_approve_confidence_threshold", 0.95
    )

    if confidence is None or confidence < threshold:
        return "manual_review"

    return "approve"


def reporting_node(state: InvoiceState) -> dict:
    """Generate final reports and persist the audit through repository.py."""

    invoice_id = state.get("invoice_id")
    if not invoice_id:
        raise ValueError("invoice_id is required for reporting")

    rules = load_rules()
    missing_fields = find_missing_fields(state, rules)

    recommendation = determine_recommendation(
        state, missing_fields, rules
    )

    errors = state.get("validation_errors") or []
    warnings = state.get("validation_warnings") or []
    discrepancies = state.get("discrepancies") or []

    if recommendation == "reject" or errors:
        validation_status = "failed"
    elif missing_fields or warnings or discrepancies:
        validation_status = "partial"
    else:
        validation_status = "passed"

    summary = (
        f"Invoice {state.get('invoice_number') or invoice_id}: "
        f"{validation_status}. "
        f"Missing fields: {len(missing_fields)}. "
        f"Discrepancies: {len(discrepancies)}. "
        f"Recommendation: {recommendation}."
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = REPORT_DIR / f"{invoice_id}.json"
    html_path = REPORT_DIR / f"{invoice_id}.html"

    report = {
        "invoice_id": invoice_id,
        "invoice_number": state.get("invoice_number"),
        "vendor_name": state.get("vendor_name"),
        "invoice_date": state.get("invoice_date"),
        "currency": state.get("currency"),
        "total_amount": state.get("total_amount"),
        "source_language": state.get("source_language"),
        "translation_confidence": state.get("translation_confidence"),
        "validation_status": validation_status,
        "recommendation": recommendation,
        "summary": summary,
        "missing_fields": missing_fields,
        "validation_errors": errors,
        "validation_warnings": warnings,
        "discrepancies": discrepancies,
        "line_items": state.get("line_items") or [],
        "report_path": str(json_path),
    }

    # Generate machine-readable JSON.
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Generate human-readable HTML.
    esc = lambda value: html.escape(str(value))

    missing_html = "".join(
        f"<li>{esc(field)}</li>" for field in missing_fields
    ) or "<li>None</li>"

    errors_html = "".join(
        f"<li>{esc(error)}</li>" for error in errors
    ) or "<li>None</li>"

    discrepancies_html = "".join(
        "<li>"
        f"{esc(item.get('field_name', 'Unknown'))}: "
        f"Invoice={esc(item.get('invoice_value'))}, "
        f"ERP={esc(item.get('erp_value'))}"
        "</li>"
        for item in discrepancies
    ) or "<li>None</li>"

    html_report = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Invoice Audit Report</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 32px; line-height: 1.5; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
</style>
</head>
<body>
<h1>Invoice Audit Report</h1>
<p><b>Invoice:</b> {esc(state.get('invoice_number') or invoice_id)}</p>
<p><b>Vendor:</b> {esc(state.get('vendor_name') or 'Unknown')}</p>
<p><b>Summary:</b> {esc(summary)}</p>
<p><b>Validation status:</b> {esc(validation_status)}</p>
<p><b>Recommendation:</b> {esc(recommendation)}</p>
<p><b>Source language:</b> {esc(state.get('source_language') or 'Unknown')}</p>
<p><b>Translation confidence:</b>
{esc(state.get('translation_confidence') if state.get('translation_confidence') is not None else 'Unavailable')}</p>
<h2>Missing Fields</h2><ul>{missing_html}</ul>
<h2>Validation Errors</h2><ul>{errors_html}</ul>
<h2>Discrepancies</h2><ul>{discrepancies_html}</ul>
</body>
</html>
"""

    html_path.write_text(html_report, encoding="utf-8")

    # PostgreSQL is the system of record.
    # If persistence fails, this node raises instead of claiming success.
    save_audit_report(
        state={
            **state,
            "validation_status": validation_status,
            "recommendation": recommendation,
        },
        report=report,
        missing_fields=missing_fields,
    )

    return {
        "report": report,
        "report_summary": summary,
        "report_generated": True,
        "report_saved": True,
        "validation_status": validation_status,
        "recommendation": recommendation,
        "current_stage": "reporting_completed",
    }


