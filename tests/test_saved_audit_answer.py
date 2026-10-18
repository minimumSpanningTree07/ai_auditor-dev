from agent import server


def test_saved_audit_answer_explains_discrepancies(monkeypatch):
    def fake_fetch_one(sql, params=None):
        return {
            "file_name": "INV_EN_005_scan.png", "invoice_number": "INV-L005",
            "vendor_name": "SwiftMove Couriers", "po_number": "PO-1005",
            "currency": None, "total_amount": 255.7500,
            "validation_status": "manual_review", "recommendation": "manual_review",
            "human_review_required": True,
        }

    def fake_fetch_all(sql, params=None):
        if "audit.discrepancies" in sql:
            return [
                {"discrepancy_type": "missing_required_field", "severity": "HIGH",
                 "message": "Required invoice field is missing: currency.", "details": {}, "status": "OPEN"},
                {"discrepancy_type": "currency_not_fully_validated", "severity": "MEDIUM",
                 "message": "Currency could not be fully validated against ERP.", "details": {}, "status": "OPEN"},
                {"discrepancy_type": "po_sku_mismatch", "severity": "HIGH",
                 "message": "Invoice line 2 SKU 'unknown' was not found in the purchase order.", "details": {}, "status": "OPEN"},
            ]
        return [{"line_number": 1, "sku": "SKU-1", "description": "Test", "quantity": 1, "unit_price": 2, "line_total": 2}]

    monkeypatch.setattr(server.db, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(server.db, "fetch_all", fake_fetch_all)
    answer, meta = server._saved_audit_answer("Why manual review? Explain each discrepancy", "invoice-id")
    assert "missing required field" in answer.lower()
    assert "currency" in answer.lower()
    assert "po sku mismatch" in answer.lower()
    assert "Verify:" in answer
    assert meta["discrepancy_count"] == 3
