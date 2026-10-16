from __future__ import annotations

from typing import Any

import streamlit as st


def render_dashboard(summary: dict[str, Any]) -> None:
    st.subheader("Dashboard")

    total = summary.get("total", 0)
    approved = summary.get("approved", 0)
    manual_review = summary.get("manual_review", 0)
    rejected = summary.get("rejected", 0)

    columns = st.columns(4)

    with columns[0]:
        st.metric("Total Invoices", total)

    with columns[1]:
        st.metric("Approved", approved)

    with columns[2]:
        st.metric("Manual Review", manual_review)

    with columns[3]:
        st.metric("Rejected", rejected)