from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def render_invoice_table(
    invoices: list[dict[str, Any]],
) -> str | None:

    if not invoices:
        st.info(
            "No invoices available."
        )
        return None

    display_rows = []

    for invoice in invoices:

        display_rows.append(
            {
                "Invoice Number": (
                    invoice.get(
                        "invoice_number"
                    )
                    or "Unknown"
                ),
                "Vendor": (
                    invoice.get(
                        "vendor_name"
                    )
                    or "Unknown"
                ),
                "PO": (
                    invoice.get(
                        "po_number"
                    )
                    or "—"
                ),
                "Date": (
                    invoice.get(
                        "invoice_date"
                    )
                    or "—"
                ),
                "Total": (
                    f"{invoice.get('currency') or ''} "
                    f"{invoice.get('total_amount') or 0}"
                ),
                "Status": (
                    invoice.get(
                        "validation_status"
                    )
                    or "unknown"
                ),
                "Recommendation": (
                    invoice.get(
                        "recommendation"
                    )
                    or "—"
                ),
            }
        )

    dataframe = pd.DataFrame(
        display_rows
    )

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )

    # ------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------

    options = {}

    for invoice in invoices:

        invoice_id = invoice.get(
            "invoice_id"
        )

        invoice_number = invoice.get("invoice_number") or "Invoice number pending"
        file_name = invoice.get("file_name") or "Unnamed file"
        vendor = invoice.get("vendor_name") or "Vendor unknown"

        if invoice_id:
            label = f"{file_name} | {invoice_number} | {vendor} | {invoice_id[:8]}"
            options[label] = invoice_id

    if not options:
        return None

    selected_label = st.selectbox(
        "Select invoice",
        list(options.keys()),
        key="selected_invoice",
    )

    return options.get(
        selected_label
    )