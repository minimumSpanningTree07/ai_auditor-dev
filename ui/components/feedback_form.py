from __future__ import annotations

from typing import Any

import streamlit as st


def render_feedback_form(
    invoice: dict[str, Any],
) -> tuple[
    str,
    str,
    dict[str, Any],
    bool,
]:
    st.subheader("Human Review")

    decision = st.selectbox(
        "Decision",
        [
            "approved",
            "manual_review",
            "rejected",
        ],
        key="feedback_decision",
    )

    feedback = st.text_area(
        "Feedback",
        placeholder=(
            "Explain the correction or review decision..."
        ),
        key="feedback_text",
    )

    st.markdown("### Corrections")

    left, right = st.columns(2)

    with left:
        invoice_number = st.text_input(
            "Invoice Number",
            value=str(
                invoice.get("invoice_number") or ""
            ),
            key="corrected_invoice_number",
        )

        vendor_name = st.text_input(
            "Vendor",
            value=str(
                invoice.get("vendor_name") or ""
            ),
            key="corrected_vendor_name",
        )

        po_number = st.text_input(
            "PO Number",
            value=str(
                invoice.get("po_number") or ""
            ),
            key="corrected_po_number",
        )

    with right:
        currency = st.text_input(
            "Currency",
            value=str(
                invoice.get("currency") or ""
            ),
            key="corrected_currency",
        )

        invoice_date = st.text_input(
            "Invoice Date",
            value=str(
                invoice.get("invoice_date") or ""
            ),
            key="corrected_invoice_date",
        )

        total_amount = st.text_input(
            "Total Amount",
            value=str(
                invoice.get("total_amount") or ""
            ),
            key="corrected_total_amount",
        )

    corrections = {
        "invoice_number": invoice_number,
        "vendor_name": vendor_name,
        "po_number": po_number,
        "currency": currency,
        "invoice_date": invoice_date,
        "total_amount": total_amount,
    }

    submitted = st.button(
        "Submit Review & Revalidate",
        type="primary",
        use_container_width=True,
    )

    return (
        decision,
        feedback,
        corrections,
        submitted,
    )