from __future__ import annotations

import streamlit as st


def render_discrepancy_panel(discrepancies: list[dict]) -> None:
    st.subheader("Discrepancies")
    if not discrepancies:
        st.success("No discrepancies found.")
        return
    st.warning(f"{len(discrepancies)} discrepancy item(s) recorded.")
    for index, item in enumerate(discrepancies, start=1):
        kind = item.get("discrepancy_type") or item.get("field") or "Discrepancy"
        severity = str(item.get("severity") or "info").upper()
        message = item.get("message") or "No message provided."
        with st.expander(f"{index}. {kind} · {severity}"):
            st.write(message)
            details = item.get("details")
            if details:
                st.json(details)
            st.caption(f"Status: {item.get('status') or 'unknown'}")
