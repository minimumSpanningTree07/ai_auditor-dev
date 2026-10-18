from __future__ import annotations

import streamlit as st


def render_dashboard(summary: dict) -> None:
    st.title("Dashboard")
    st.caption("AI Invoice Auditor")

    columns = st.columns(4)
    metrics = [
        ("Total invoices", summary.get("total_invoices", 0)),
        ("Approved", summary.get("approved_invoices", 0)),
        ("Needs review", summary.get("review_invoices", 0)),
        ("Pending review", summary.get("pending_review", 0)),
    ]
    for column, (label, value) in zip(columns, metrics):
        column.metric(label, value or 0)

    st.divider()
    st.subheader("Discrepancies")
    cols = st.columns(3)
    cols[0].metric("Total", summary.get("total_discrepancies", 0) or 0)
    cols[1].metric("Open", summary.get("open_discrepancies", 0) or 0)
    cols[2].metric("High severity", summary.get("high_severity_discrepancies", 0) or 0)
