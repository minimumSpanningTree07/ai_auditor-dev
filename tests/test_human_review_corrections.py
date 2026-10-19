from agent.nodes.persistence import _build_effective_line_items
from agent.nodes.reporting import _determine_outcome


def test_line_number_correction_keeps_a_single_effective_line():
    state = {
        "extracted_line_items": [
            {"item_code": "SKU-OLD", "description": "Gloves", "quantity": "2", "unit_price": "3.50"},
            {"item_code": "SKU-OTHER", "description": "Helmets", "quantity": "1", "unit_price": "15.00"},
        ],
        "human_corrections": {
            "line_items": [
                {"line_number": 1, "sku": "SKU-CORRECT", "quantity": 2, "unit_price": "3.00"}
            ]
        },
    }
    items = _build_effective_line_items(state)
    assert len(items) == 2
    assert items[0]["sku"] == "SKU-CORRECT"
    assert items[0]["item_code"] == "SKU-CORRECT"
    assert items[0]["line_total"] == "6"
    assert items[1]["item_code"] == "SKU-OTHER"
    # Original extraction remains immutable.
    assert state["extracted_line_items"][0]["item_code"] == "SKU-OLD"


def test_correct_and_revalidate_approves_only_when_current_checks_pass():
    passed = {
        "human_decision": "corrected",
        "data_validation_passed": True,
        "business_validation_passed": True,
        "erp_lookup_failed": False,
        "missing_erp_records": [],
        "missing_fields": [],
    }
    assert _determine_outcome(passed, []) == ("approved", "approve", False)

    failed = {**passed, "business_validation_passed": False}
    findings = [{"type": "po_unit_price_mismatch", "severity": "high", "status": "open"}]
    assert _determine_outcome(failed, findings) == ("manual_review", "manual_review", True)


def test_explicit_approval_keeps_findings_visible_in_report_state():
    finding = {"type": "po_unit_price_mismatch", "severity": "high", "status": "open"}
    assert _determine_outcome({"human_decision": "approved"}, [finding]) == (
        "approved", "approve", False
    )
