from __future__ import annotations

from typing import Any

import streamlit as st


def render_invoice_table(
    invoices: list[dict[str, Any]],
) -> str | None:
    if not invoices:
        st.info("No invoices available.")
        return None

    rows = [
        {
            "Invoice": invoice.get("invoice_number") or "-",
            "Vendor": invoice.get("vendor_name") or "-",
            "PO": invoice.get("po_number") or "-",
            "Date": invoice.get("invoice_date") or "-",
            "Currency": invoice.get("currency") or "-",
            "Total": invoice.get("total_amount") or "-",
            "Status": invoice.get(
                "validation_status"
            ) or "-",
        }
        for invoice in invoices
    ]

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )

    options = {
        invoice.get("invoice_id"): (
            f"{invoice.get('invoice_number') or 'Unknown'}"
            f" — "
            f"{invoice.get('vendor_name') or 'Unknown Vendor'}"
        )
        for invoice in invoices
    }

    return st.selectbox(
        "Select Invoice",
        options=list(options.keys()),
        format_func=lambda value: options[value],
    )