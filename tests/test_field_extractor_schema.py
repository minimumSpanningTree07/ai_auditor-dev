import re
from pathlib import Path


from agents.nodes.field_extractor import extract_invoice_fields




RAW_TEXT = """
Invoice No: INV-2048
Date: 2026-10-15
Vendor: Northwind Trading
Currency: USD
Total: $1,254.80


Line Items:
1. SKU-100 | Widget A | 2 | 45.00 | 90.00
2. SKU-200 | Widget B | 3 | 388.27 | 1164.81
"""




def test_field_extractor_extracts_core_fields():
    result = extract_invoice_fields({
        "raw_extracted_text": "Invoice No: INV-2048\nPO No: PO-1001\nDate: 2026-10-15\nVendor: Northwind Trading\nCurrency: USD\nTotal: $1,254.80\n\nLine Items:\n1. SKU-100 | Widget A | 2 | 45.00 | 90.00\n2. SKU-200 | Widget B | 3 | 388.27 | 1164.81\n"
    })


    assert result["invoice_number"] == "INV-2048"
    assert result["po_number"] == "PO-1001"
    assert result["invoice_date"] == "2026-10-15"
    assert result["vendor_name"] == "Northwind Trading"
    assert result["currency"] == "USD"
    assert result["total_amount"] == 1254.80
    assert len(result["line_items"]) >= 2
    assert result["line_items"][0]["item_code"] == "SKU-100"
    assert result["line_items"][0]["line_total"] == 90.00




def test_field_extractor_does_not_guess_a_po_number_from_invoice_number():
    result = extract_invoice_fields({"raw_extracted_text": "Invoice No: INV-2048\nVendor: Northwind Trading\nTotal: $123.45"})
    assert result["po_number"] is None




def test_database_schema_and_state_match_for_invoice_audit():
    state_file = Path("agents/state.py").read_text(encoding="utf-8")
    schema_sql = Path("database/audit.schema.sql").read_text(encoding="utf-8")


    state_keys = set(re.findall(r"^\s{2,}([A-Za-z_]+):", state_file, flags=re.M))
    schema_columns = set(re.findall(r"\n\s{4}([A-Za-z_]+)\s+[A-Z0-9\(\),\s]+", schema_sql, flags=re.M))


    invoice_audit_columns = {
        "invoice_id",
        "file_path",
        "file_checksum",
        "extraction_method",
        "raw_extracted_text",
        "translated_text",
        "source_language",
        "translation_confidence",
        "invoice_number",
        "vendor_id",
        "vendor_name",
        "po_number",
        "invoice_date",
        "currency",
        "total_amount",
        "validation_status",
        "recommendation",
        "extracted_raw",
        "thread_id",
        "processed_at",
    }


    assert invoice_audit_columns.issubset(schema_columns)
    assert {"invoice_number", "currency", "total_amount", "vendor_name"}.issubset(state_keys)


