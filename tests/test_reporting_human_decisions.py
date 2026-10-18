from agent.nodes.reporting import _determine_outcome


def test_explicit_human_approval_updates_status_even_with_open_findings():
    state = {
        "human_decision": "approved",
        "data_validation_passed": False,
        "business_validation_passed": False,
        "human_review_required": True,
    }
    findings = [{"type": "po_unit_price_mismatch", "status": "open"}]

    assert _determine_outcome(state, findings) == ("approved", "approve", False)


def test_corrected_invoice_can_pass_despite_stale_review_flag():
    state = {
        "human_decision": "corrected",
        "data_validation_passed": True,
        "business_validation_passed": True,
        "human_review_required": True,
        "erp_lookup_failed": False,
        "missing_erp_records": [],
        "missing_fields": [],
    }

    assert _determine_outcome(state, []) == ("approved", "approve", False)


def test_corrected_invoice_stays_in_review_if_findings_remain():
    state = {
        "human_decision": "corrected",
        "data_validation_passed": True,
        "business_validation_passed": False,
        "human_review_required": True,
        "erp_lookup_failed": False,
        "missing_erp_records": [],
        "missing_fields": [],
    }
    findings = [{"type": "po_unit_price_mismatch", "status": "open"}]

    assert _determine_outcome(state, findings) == ("manual_review", "manual_review", True)


def test_rejection_is_persisted_as_rejected():
    assert _determine_outcome({"human_decision": "rejected"}, []) == ("rejected", "reject", False)
