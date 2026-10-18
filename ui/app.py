from __future__ import annotations

import streamlit as st

from api_client import (
    AgentAPIError,
    health,
    get_dashboard_summary,
    get_invoices,
    get_invoice,
    upload_invoice,
    revalidate_invoice,
    ask_ai,
)

from components.dashboard import render_dashboard
from components.invoice_table import render_invoice_table
from components.invoice_details import render_invoice_details
from components.discrepancy_panel import render_discrepancy_panel


st.set_page_config(
    page_title="AI Invoice Auditor",
    page_icon="🧾",
    layout="wide",
)


def main() -> None:

    st.sidebar.title("AI Invoice Auditor")

    try:
        health()
        agent_online = True
    except AgentAPIError:
        agent_online = False

    if agent_online:
        st.sidebar.success("Agent Online")
    else:
        st.sidebar.error("Agent Offline")

    page = st.sidebar.radio(
        "Navigation",
        [
            "Dashboard",
            "Invoices",
            "Upload Invoice",
            "Ask AI",
        ],
    )

    if page == "Dashboard":
        dashboard_page()

    elif page == "Invoices":
        invoices_page()

    elif page == "Upload Invoice":
        upload_page()

    elif page == "Ask AI":
        ask_ai_page()


def dashboard_page() -> None:

    st.title("AI Invoice Auditor")

    try:
        summary = get_dashboard_summary()
        render_dashboard(summary)

    except AgentAPIError as exc:
        st.error(str(exc))


def invoices_page() -> None:

    st.title("Invoices")

    try:
        invoices = get_invoices()

        selected_id = render_invoice_table(
            invoices
        )

        if not selected_id:
            return

        invoice = get_invoice(selected_id)

        st.divider()

        render_invoice_details(invoice)

        discrepancies = invoice.get(
            "discrepancies",
            [],
        )

        render_discrepancy_panel(
            discrepancies
        )

        st.divider()

        render_hitl(
            invoice=invoice,
            invoice_id=selected_id,
        )

    except AgentAPIError as exc:
        st.error(str(exc))


def render_hitl(
    invoice: dict,
    invoice_id: str,
) -> None:

    status = str(
        invoice.get(
            "validation_status",
            "",
        )
    ).lower()

    review_required = bool(
        invoice.get(
            "human_review_required",
            False,
        )
    )

    if (
        status != "manual_review"
        and not review_required
    ):
        st.success(
            "No human review required."
        )
        return

    st.warning(
        "Human review required"
    )

    st.subheader(
        "Human-in-the-Loop Review"
    )

    st.caption(
        "Review the extracted values, "
        "correct discrepancies if required, "
        "then revalidate the invoice."
    )

    line_items = invoice.get(
        "line_items",
        [],
    )

    corrections = {
        "line_items": []
    }

    if line_items:

        st.markdown(
            "### Correct Line Items"
        )

        for index, item in enumerate(
            line_items
        ):

            sku = (
                item.get("sku")
                or item.get("sku_code")
                or item.get("product_code")
                or ""
            )

            st.markdown(
                f"**{sku}**"
            )

            col1, col2 = st.columns(2)

            original_quantity = float(
                item.get(
                    "quantity",
                    0,
                ) or 0
            )

            original_unit_price = float(
                item.get(
                    "unit_price",
                    0,
                ) or 0
            )

            with col1:

                quantity = st.number_input(
                    "Quantity",
                    min_value=0.0,
                    value=original_quantity,
                    step=1.0,
                    key=f"qty_{invoice_id}_{index}",
                )

            with col2:

                unit_price = st.number_input(
                    "Unit Price",
                    min_value=0.0,
                    value=original_unit_price,
                    step=0.01,
                    format="%.2f",
                    key=f"price_{invoice_id}_{index}",
                )

            correction = {
                "sku": sku,
            }

            changed = False

            if quantity != original_quantity:
                correction["quantity"] = quantity
                changed = True

            if unit_price != original_unit_price:
                correction["unit_price"] = unit_price
                changed = True

            if changed:
                corrections["line_items"].append(
                    correction
                )

    feedback = st.text_area(
        "Auditor feedback",
        placeholder=(
            "Explain the correction or "
            "review decision..."
        ),
        key=f"feedback_{invoice_id}",
    )

    decision = st.selectbox(
        "Decision",
        [
            "Correct & Revalidate",
            "Approve",
            "Reject",
        ],
        key=f"decision_{invoice_id}",
    )

    if st.button(
        "Submit Human Review",
        type="primary",
        key=f"submit_hitl_{invoice_id}",
    ):

        if decision == "Correct & Revalidate":

            api_decision = "corrected"

        elif decision == "Approve":

            api_decision = "approved"

        else:

            api_decision = "rejected"

        correction_payload = {}

        if corrections["line_items"]:
            correction_payload[
                "line_items"
            ] = corrections["line_items"]

        try:

            with st.spinner(
                "Applying human review and revalidating..."
            ):

                result = revalidate_invoice(
                    invoice_id=invoice_id,
                    corrections=correction_payload,
                    decision=api_decision,
                    feedback=feedback.strip() or None,
                )

            st.success(
                "Human review submitted successfully."
            )

            st.json(result)

            st.rerun()

        except AgentAPIError as exc:

            st.error(str(exc))


def upload_page() -> None:

    st.title("Upload Invoice")

    st.caption(
        "Supported formats: PDF, DOCX and PNG"
    )

    uploaded_file = st.file_uploader(
        "Choose an invoice",
        type=[
            "pdf",
            "docx",
            "png",
        ],
    )

    if uploaded_file is None:
        return

    st.info(
        f"Selected: {uploaded_file.name}"
    )

    if st.button(
        "Upload Invoice",
        type="primary",
    ):

        try:

            with st.spinner(
                "Uploading invoice..."
            ):

                result = upload_invoice(
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                )

            st.success(
                result.get(
                    "message",
                    "Invoice uploaded successfully.",
                )
            )

            st.json(result)

        except AgentAPIError as exc:

            st.error(str(exc))


def ask_ai_page() -> None:

    st.title("Ask AI")

    st.caption(
        "Ask questions about invoices and audit results using RAG."
    )

    try:

        invoices = get_invoices()

    except AgentAPIError as exc:

        st.error(str(exc))
        return

    invoice_options = [
        {
            "label": "All invoices",
            "id": None,
        }
    ]

    seen_numbers = set()

    for invoice in invoices:

        invoice_number = (
            invoice.get("invoice_number")
            or invoice.get("file_name")
            or "Unknown"
        )

        invoice_id = invoice.get(
            "invoice_id"
        )

        if not invoice_id:
            continue

        # Avoid duplicate invoice-number entries.
        if invoice_number in seen_numbers:
            continue

        seen_numbers.add(invoice_number)

        invoice_options.append(
            {
                "label": str(invoice_number),
                "id": invoice_id,
            }
        )

    selected_invoice = st.selectbox(
        "Invoice",
        options=invoice_options,
        format_func=lambda item: item["label"],
    )

    question = st.text_area(
        "Question",
        placeholder=(
            "Examples:\n"
            "• What is the total amount?\n"
            "• What discrepancies were found?\n"
            "• Why was this invoice sent for manual review?\n"
            "• What is the PO number?"
        ),
        height=120,
    )

    if st.button(
        "Ask AI",
        type="primary",
    ):

        if not question.strip():

            st.warning(
                "Please enter a question."
            )

            return

        try:

            with st.spinner(
                "Searching invoices and generating answer..."
            ):

                result = ask_ai(
                    question=question.strip(),
                    invoice_id=selected_invoice[
                        "id"
                    ],
                )

            st.subheader(
                "Answer"
            )

            st.success(
                result.get(
                    "answer",
                    "No answer returned.",
                )
            )

            reflection = result.get(
                "reflection",
                {},
            )

            if reflection:

                st.divider()

                st.subheader(
                    "RAG Evaluation"
                )

                col1, col2, col3, col4 = st.columns(
                    4
                )

                with col1:
                    st.metric(
                        "Context Relevance",
                        round(
                            float(
                                reflection.get(
                                    "context_relevance",
                                    0,
                                )
                            ),
                            3,
                        ),
                    )

                with col2:
                    st.metric(
                        "Groundedness",
                        round(
                            float(
                                reflection.get(
                                    "groundedness",
                                    0,
                                )
                            ),
                            3,
                        ),
                    )

                with col3:
                    st.metric(
                        "Question Relevance",
                        round(
                            float(
                                reflection.get(
                                    "question_relevance",
                                    0,
                                )
                            ),
                            3,
                        ),
                    )

                with col4:

                    overall = float(
                        reflection.get(
                            "overall_score",
                            0,
                        )
                    )

                    if overall > 0.7:
                        st.metric(
                            "Overall",
                            f"{overall:.3f}",
                        )
                    else:
                        st.metric(
                            "Overall",
                            f"{overall:.3f}",
                            delta="Below threshold",
                        )

                reason = reflection.get(
                    "reason"
                )

                if reason:

                    st.caption(
                        f"Evaluation: {reason}"
                    )

            retry_count = result.get(
                "retry_count",
                0,
            )

            if retry_count:

                st.caption(
                    f"RAG retries used: {retry_count}"
                )

        except AgentAPIError as exc:

            st.error(str(exc))


if __name__ == "__main__":
    main()