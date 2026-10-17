from pathlib import Path

from docx import Document

from agent.nodes.extraction import _extract_document_text, _estimate_confidence


def test_docx_extraction_includes_paragraphs_and_table(tmp_path: Path):
    path = tmp_path / "invoice.docx"
    document = Document()
    document.add_paragraph("Invoice INV-100")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Item A"
    table.cell(0, 1).text = "12.50"
    document.save(path)

    text, method = _extract_document_text(path)

    assert method == "docx"
    assert "Invoice INV-100" in text
    assert "Item A | 12.50" in text


def test_extraction_confidence_is_bounded():
    confidence = _estimate_confidence(
        "Invoice date 2026-01-01\nPO: PO-10\nTax\nTotal USD 10.00",
        "pdf_text",
    )
    assert 0.0 <= confidence <= 1.0
