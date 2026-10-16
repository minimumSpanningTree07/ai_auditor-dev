from __future__ import annotations

from typing import Any

import streamlit as st


def render_discrepancy_panel(
    discrepancies: list[dict[str, Any]],
) -> None:
    st.subheader("Discrepancies")

    if not discrepancies:
        st.success("No discrepancies detected.")
        return

    for index, discrepancy in enumerate(
        discrepancies,
        start=1,
    ):
        severity = str(
            discrepancy.get("severity")
            or "warning"
        ).lower()

        message = (
            discrepancy.get("message")
            or "Discrepancy detected."
        )

        if severity == "critical":
            st.error(
                f"Critical — {message}"
            )
        elif severity == "error":
            st.error(
                f"Error — {message}"
            )
        elif severity == "warning":
            st.warning(
                f"Warning — {message}"
            )
        else:
            st.info(
                f"{severity.title()} — {message}"
            )

        details = discrepancy.get("details")

        if details:
            with st.expander(
                f"Details {index}"
            ):
                if isinstance(details, dict):
                    st.json(details)
                else:
                    st.write(details)