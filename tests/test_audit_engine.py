from app.services.audit_engine import AuditEngine




def test_valid_invoice_matches_po_and_is_approved():
    invoice = {
        "invoice_no": "INV-9001",
        "invoice_date": "2026-10-15",
        "vendor_id": "VEND-001",
        "currency": "USD",
        "total_amount": 1410.0,
        "line_items": [
            {"item_code": "SKU-001", "description": "Pallet Wrapping Film", "qty": 50, "unit_price": 12.0, "total": 600.0},
            {"item_code": "SKU-002", "description": "Industrial Gloves", "qty": 120, "unit_price": 3.0, "total": 360.0},
            {"item_code": "SKU-003", "description": "Safety Helmets", "qty": 30, "unit_price": 15.0, "total": 450.0},
        ],
    }


    engine = AuditEngine(rules_path="config/rules.yaml", mock_data_dir="data/ERP_mockdata")
    result = engine.run_audit(invoice)


    assert result["status"] == "approved"
    assert result["matched_po"] == "PO-1001"
    assert result["exceptions"] == []




def test_invalid_currency_is_rejected():
    invoice = {
        "invoice_no": "INV-9002",
        "invoice_date": "2026-10-15",
        "vendor_id": "VEND-003",
        "currency": "JPY",
        "total_amount": 100.0,
        "line_items": [
            {"item_code": "SKU-201", "description": "Cajas de carton", "qty": 10, "unit_price": 10.0, "total": 100.0}
        ],
    }


    engine = AuditEngine(rules_path="config/rules.yaml", mock_data_dir="data/ERP_mockdata")
    result = engine.run_audit(invoice)


    assert result["status"] == "rejected"
    assert any("currency" in issue.lower() for issue in result["issues"])
