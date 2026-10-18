# from __future__ import annotations

# from typing import Any

# import streamlit as st


# def render_dashboard(summary: dict[str, Any]) -> None:
#     st.subheader("Dashboard")

#     total = summary.get("total", 0)
#     approved = summary.get("approved", 0)
#     manual_review = summary.get("manual_review", 0)
#     rejected = summary.get("rejected", 0)

#     columns = st.columns(4)

#     with columns[0]:
#         st.metric("Total Invoices", total)

#     with columns[1]:
#         st.metric("Approved", approved)

#     with columns[2]:
#         st.metric("Manual Review", manual_review)

#     with columns[3]:
#         st.metric("Rejected", rejected)

from __future__ import annotations

import streamlit as st


def render_dashboard(summary: dict) -> None:

    st.title("Dashboard")
    st.caption("AI Invoice Auditor")

    total = summary.get("total_invoices", 0)
    pending = summary.get("pending", 0)
    approved = summary.get("approved", 0)
    review = summary.get("manual_review", 0)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Invoices",
            total,
        )

    with col2:
        st.metric(
            "Pending",
            pending,
        )

    with col3:
        st.metric(
            "Approved",
            approved,
        )

    with col4:
        st.metric(
            "Manual Review",
            review,
        )

    st.divider()

    st.subheader("Recent Invoices")