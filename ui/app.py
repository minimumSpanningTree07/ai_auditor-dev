from __future__ import annotations

import streamlit as st

from api_client import api_client


st.set_page_config(
    page_title="AI Invoice Auditor",
    page_icon="📄",
    layout="wide",
)


def safe_call(function, default):
    try:
        return function()
    except Exception as exc:
        st.error(str(exc))
        return default


def status_badge(status: str | None) -> str:
    value = (status or "unknown").lower()

    if value == "approved":
        return "🟢 Approved"

    if value == "manual_review":
        return "🟡 Manual Review"

    if value == "rejected":
        return "🔴 Rejected"

    return "⚪ Unknown"


st.title("AI Invoice Auditor")
st.caption(
    "Invoice extraction, ERP validation, discrepancy detection and RAG-assisted audit."
)

# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------

with st.sidebar:
    st.header("Invoice Upload")

    uploaded_file = st.file_uploader(
        "Add a new invoice",
        type=[
            "pdf",
            "png",
            "jpg",
            "jpeg",
            "tif",
            "tiff",
        ],
    )

    if uploaded_file is not None:
        if st.button(
            "Upload Invoice",
            use_container_width=True,
        ):
            try:
                result = api_client.upload_invoice(
                    uploaded_file
                )

                st.success(
                    result.get(
                        "message",
                        "Invoice uploaded.",
                    )
                )

                st.rerun()

            except Exception as exc:
                st.error(str(exc))

    st.divider()

    if st.button(
        "Refresh",
        use_container_width=True,
    ):
        st.rerun()


# ------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------

summary = safe_call(
    api_client.dashboard_summary,
    {
        "total": 0,
        "approved": 0,
        "manual_review": 0,
        "rejected": 0,
    },
)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Invoices",
        summary.get("total", 0),
    )

with col2:
    st.metric(
        "Approved",
        summary.get("approved", 0),
    )

with col3:
    st.metric(
        "Manual Review",
        summary.get("manual_review", 0),
    )

with col4:
    st.metric(
        "Rejected",
        summary.get("rejected", 0),
    )

st.divider()


# ------------------------------------------------------------------
# Invoice List
# ------------------------------------------------------------------

st.subheader("Invoices")

invoices = safe_call(
    api_client.get_invoices,
    [],
)

if not invoices:
    st.info(
        "No invoices available. Upload an invoice to begin."
    )
    st.stop()


invoice_labels = {
    invoice.get("invoice_id"): (
        f"{invoice.get('invoice_number') or 'Unknown'}"
        f" — "
        f"{invoice.get('vendor_name') or 'Unknown Vendor'}"
    )
    for invoice in invoices
}

selected_id = st.selectbox(
    "Select Invoice",
    options=list(invoice_labels.keys()),
    format_func=lambda value: invoice_labels[value],
)

selected = next(
    (
        invoice
        for invoice in invoices
        if invoice.get("invoice_id") == selected_id
    ),
    None,
)

if selected:
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.write("**Invoice**")
        st.write(
            selected.get(
                "invoice_number",
                "-",
            )
        )

    with c2:
        st.write("**Vendor**")
        st.write(
            selected.get(
                "vendor_name",
                "-",
            )
        )

    with c3:
        st.write("**PO**")
        st.write(
            selected.get(
                "po_number",
                "-",
            )
        )

    with c4:
        st.write("**Status**")
        st.write(
            status_badge(
                selected.get(
                    "validation_status"
                )
            )
        )


# ------------------------------------------------------------------
# Invoice Details
# ------------------------------------------------------------------

try:
    invoice = api_client.get_invoice(
        selected_id
    )
except Exception as exc:
    st.error(str(exc))
    st.stop()

tab_details, tab_discrepancies, tab_feedback = st.tabs(
    [
        "Invoice Details",
        "Discrepancies",
        "Human Review",
    ]
)


with tab_details:
    st.subheader("Invoice Information")

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

    with right:
        st.write(
            "**Currency:**",
            invoice.get("currency") or "-",
        )
        st.write(
            "**Subtotal:**",
            invoice.get("subtotal_amount") or "-",
        )
        st.write(
            "**Tax:**",
            invoice.get("tax_amount") or "-",
        )
        st.write(
            "**Total:**",
            invoice.get("total_amount") or "-",
        )

    st.subheader("Line Items")

    line_items = invoice.get(
        "line_items",
        [],
    )

    if line_items:
        st.dataframe(
            line_items,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No line items available.")

    st.subheader("Recommendation")

    st.info(
        invoice.get(
            "recommendation",
            "No recommendation available.",
        )
    )


with tab_discrepancies:
    discrepancies = invoice.get(
        "discrepancies",
        [],
    )

    if not discrepancies:
        st.success(
            "No discrepancies recorded."
        )
    else:
        for discrepancy in discrepancies:
            severity = str(
                discrepancy.get(
                    "severity",
                    "warning",
                )
            ).upper()

            st.warning(
                f"{severity}: "
                f"{discrepancy.get('message', 'Discrepancy detected')}"
            )

            details = discrepancy.get(
                "details"
            )

            if details:
                st.json(details)


with tab_feedback:
    st.subheader("Human Review")

    current_status = invoice.get(
        "validation_status"
    )

    st.write(
        f"Current status: "
        f"**{status_badge(current_status)}**"
    )

    decision = st.selectbox(
        "Decision",
        [
            "approved",
            "manual_review",
            "rejected",
        ],
    )

    feedback = st.text_area(
        "Feedback",
        placeholder=(
            "Explain the correction or review decision..."
        ),
    )

    st.markdown("### Corrections")

    col1, col2 = st.columns(2)

    with col1:
        corrected_vendor = st.text_input(
            "Vendor",
            value=invoice.get(
                "vendor_name"
            ) or "",
        )

        corrected_invoice_number = st.text_input(
            "Invoice Number",
            value=invoice.get(
                "invoice_number"
            ) or "",
        )

        corrected_po = st.text_input(
            "PO Number",
            value=invoice.get(
                "po_number"
            ) or "",
        )

    with col2:
        corrected_currency = st.text_input(
            "Currency",
            value=invoice.get(
                "currency"
            ) or "",
        )

        corrected_total = st.text_input(
            "Total Amount",
            value=str(
                invoice.get(
                    "total_amount"
                ) or ""
            ),
        )

    if st.button(
        "Submit Review & Revalidate",
        type="primary",
        use_container_width=True,
    ):
        corrections = {
            "vendor_name": corrected_vendor,
            "invoice_number": corrected_invoice_number,
            "po_number": corrected_po,
            "currency": corrected_currency,
            "total_amount": corrected_total,
        }

        try:
            result = api_client.revalidate_invoice(
                invoice_id=selected_id,
                corrections=corrections,
                decision=decision,
                feedback=feedback,
            )

            st.success(
                "Invoice revalidated successfully."
            )

            st.json(result)

            st.rerun()

        except Exception as exc:
            st.error(str(exc))


# ------------------------------------------------------------------
# Existing Feedback
# ------------------------------------------------------------------

feedback_items = invoice.get(
    "feedback",
    [],
)

if feedback_items:
    st.divider()
    st.subheader("Review History")

    st.dataframe(
        feedback_items,
        use_container_width=True,
        hide_index=True,
    )