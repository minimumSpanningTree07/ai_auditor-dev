from __future__ import annotations

from typing import Any

import streamlit as st


def render_invoice_details(
    invoice: dict[str, Any],
) -> None:
    st.subheader("Invoice Details")

    left, right = st.columns(2)

    with left:
        st.write(
            "**Invoice Number:**",
            invoice.get("invoice_number") or "-",
        )
        st.write(
            "**Vendor:**",
            invoice.get("vendor_name") or "-",
        )
        st.write(
            "**PO Number:**",
            invoice.get("po_number") or "-",
        )
        st.write(
            "**Invoice Date:**",
            invoice.get("invoice_date") or "-",
        )
        st.write(
            "**Currency:**",
            invoice.get("currency") or "-",
        )

    with right:
        st.write(
            "**Subtotal:**",
            invoice.get("subtotal_amount") or "-",
        )
        st.write(
            "**Tax:**",
            invoice.get("tax_amount") or "-",
        )
        st.write(
            "**Tax Rate:**",
            invoice.get("tax_rate") or "-",
        )
        st.write(
            "**Total:**",
            invoice.get("total_amount") or "-",
        )
        st.write(
            "**Status:**",
            invoice.get("validation_status") or "-",
        )

    st.divider()

    st.subheader("Line Items")

    line_items = invoice.get("line_items") or []

    if line_items:
        st.dataframe(
            line_items,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No line items available.")

    st.subheader("Recommendation")

    recommendation = invoice.get("recommendation")

    if recommendation:
        st.info(recommendation)
    else:
        st.info("No recommendation available.")