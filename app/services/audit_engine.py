from __future__ import annotations


import json
from decimal import Decimal
from pathlib import Path
from typing import Any


import yaml




class AuditEngine:
    """Deterministic invoice audit service used by the application and tests."""


    def __init__(self, rules_path: str = "config/rules.yaml", mock_data_dir: str = "data/ERP_mockdata") -> None:
        self.rules_path = Path(rules_path)
        self.mock_data_dir = Path(mock_data_dir)
        self.rules = self._load_yaml(self.rules_path)
        self.purchase_orders = self._load_json(self.mock_data_dir / "purchase_orders.json")


    def _load_yaml(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}


    def _load_json(self, path: Path) -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle) or []


    def _decimal(self, value: Any) -> Decimal:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))


    def _normalize_currency(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text:
            return ""
        symbol_map = self.rules.get("currency_symbol_map", {})
        if text.upper() in {str(code).upper() for code in symbol_map.values()}:
            return text.upper()
        return symbol_map.get(text, text).upper()


    def _find_matching_po(self, invoice: dict[str, Any]) -> tuple[str | None, list[str]]:
        vendor_id = invoice.get("vendor_id")
        if not vendor_id:
            return None, ["vendor_id is required"]


        matching_po = None
        issues: list[str] = []
        invoice_lines = invoice.get("line_items") or []
        invoice_map = {
            str(line.get("item_code", "")).strip(): line
            for line in invoice_lines
            if line.get("item_code")
        }


        for po in self.purchase_orders:
            if str(po.get("vendor_id", "")).strip() != str(vendor_id).strip():
                continue


            po_lines = po.get("line_items") or []
            po_map = {
                str(item.get("item_code", "")).strip(): item
                for item in po_lines
                if item.get("item_code")
            }


            if not invoice_map:
                issues.append("No invoice line items were supplied")
                continue


            missing_items = sorted(set(invoice_map) - set(po_map))
            if missing_items:
                issues.append(f"Invoice items do not match PO {po.get('po_number')}: {', '.join(missing_items)}")
                continue


            for item_code, invoice_line in invoice_map.items():
                po_line = po_map.get(item_code)
                if po_line is None:
                    continue


                invoice_qty = self._decimal(invoice_line.get("qty", 0))
                po_qty = self._decimal(po_line.get("qty", 0))
                invoice_unit = self._decimal(invoice_line.get("unit_price", 0))
                po_unit = self._decimal(po_line.get("unit_price", 0))
                invoice_total = self._decimal(invoice_line.get("total", invoice_qty * invoice_unit))
                po_total = self._decimal(po_line.get("total", po_qty * po_unit))


                if invoice_qty != po_qty:
                    issues.append(f"Quantity mismatch for {item_code}: invoice={invoice_qty}, po={po_qty}")
                if po_unit != 0 and abs(invoice_unit - po_unit) / po_unit > Decimal("0.05"):
                    issues.append(f"Price variance exceeds tolerance for {item_code}")
                if abs(invoice_total - po_total) > Decimal("0.01"):
                    issues.append(f"Line total mismatch for {item_code}: invoice={invoice_total}, po={po_total}")


            invoice_total = self._decimal(invoice.get("total_amount", 0))
            po_total = sum(
                (self._decimal(item.get("qty", 0)) * self._decimal(item.get("unit_price", 0)))
                for item in po_lines
            )
            if abs(invoice_total - po_total) > Decimal("0.01"):
                issues.append(
                    f"Invoice total mismatch against PO {po.get('po_number')}: invoice={invoice_total}, po={po_total}"
                )


            matching_po = po.get("po_number")
            break


        return matching_po, issues


    def run_audit(self, invoice: dict[str, Any]) -> dict[str, Any]:
        rules = self.rules
        header_fields = rules.get("required_fields", {}).get("header", [])
        line_fields = rules.get("required_fields", {}).get("line_item", [])
        accepted_currencies = {str(code).upper() for code in rules.get("accepted_currencies", [])}
        issues: list[str] = []


        for field in header_fields:
            if invoice.get(field) in (None, ""):
                issues.append(f"Missing required field: {field}")


        normalized_currency = self._normalize_currency(invoice.get("currency"))
        if normalized_currency:
            invoice["currency"] = normalized_currency


        if invoice.get("currency") and str(invoice.get("currency")).upper() not in accepted_currencies:
            issues.append("currency is not accepted by the validation rules")


        line_items = invoice.get("line_items") or []
        if not line_items:
            issues.append("At least one invoice line item is required")


        for index, line in enumerate(line_items, start=1):
            for field in line_fields:
                if line.get(field) in (None, ""):
                    issues.append(f"Line {index} is missing required field: {field}")


        matched_po, po_issues = self._find_matching_po(invoice)
        issues.extend(po_issues)


        if issues:
            return {
                "status": "rejected",
                "matched_po": matched_po,
                "issues": issues,
                "exceptions": [],
            }


        return {
            "status": "approved",
            "matched_po": matched_po,
            "issues": [],
            "exceptions": [],
        }



