# from __future__ import annotations

# from typing import Any

# import streamlit as st


# def render_discrepancy_panel(
#     discrepancies: list[dict[str, Any]],
# ) -> None:
#     st.subheader("Discrepancies")

#     if not discrepancies:
#         st.success("No discrepancies detected.")
#         return

#     for index, discrepancy in enumerate(
#         discrepancies,
#         start=1,
#     ):
#         severity = str(
#             discrepancy.get("severity")
#             or "warning"
#         ).lower()

#         message = (
#             discrepancy.get("message")
#             or "Discrepancy detected."
#         )

#         if severity == "critical":
#             st.error(
#                 f"Critical — {message}"
#             )
#         elif severity == "error":
#             st.error(
#                 f"Error — {message}"
#             )
#         elif severity == "warning":
#             st.warning(
#                 f"Warning — {message}"
#             )
#         else:
#             st.info(
#                 f"{severity.title()} — {message}"
#             )

#         details = discrepancy.get("details")

#         if details:
#             with st.expander(
#                 f"Details {index}"
#             ):
#                 if isinstance(details, dict):
#                     st.json(details)
#                 else:
#                     st.write(details)

from __future__ import annotations

import streamlit as st


def render_discrepancy_panel(
    discrepancies: list[dict],
) -> None:

    st.subheader("Discrepancies")

    if not discrepancies:
        st.success("No discrepancies found.")
        return

    st.warning(
        f"{len(discrepancies)} discrepancy "
        f"{'was' if len(discrepancies) == 1 else 'were'} found."
    )

    for index, discrepancy in enumerate(
        discrepancies,
        start=1,
    ):
        field = discrepancy.get(
            "field",
            "Unknown field",
        )

        invoice_value = discrepancy.get(
            "invoice_value",
            discrepancy.get("value"),
        )

        po_value = discrepancy.get(
            "po_value",
            discrepancy.get("expected"),
        )

        deviation = discrepancy.get(
            "deviation",
            "-",
        )

        with st.expander(
            f"{index}. {field}"
        ):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.write("**Invoice value**")
                st.write(invoice_value)

            with col2:
                st.write("**ERP / PO value**")
                st.write(po_value)

            with col3:
                st.write("**Deviation**")
                st.write(deviation)