from agent.rag.augmentation import augment


def test_augment_exposes_compatible_sufficiency_flags():
    docs = [{
        "id": "point-1", "score": 0.82, "invoice_id": "inv-1",
        "invoice_number": "INV-1", "vendor_name": "Example Ltd",
        "file_name": "invoice.pdf", "text": "Total amount is USD 125.00",
    }]
    result = augment(docs)
    assert result["has_sufficient_context"] is True
    assert result["sufficient"] is True
    assert "USD 125.00" in result["context"]


def test_augment_empty_documents_reports_no_context():
    result = augment([])
    assert result["has_sufficient_context"] is False
    assert result["sufficient"] is False
    assert result["context"] == ""
