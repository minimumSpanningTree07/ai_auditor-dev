
import os
import json
from datetime import datetime
from decimal import Decimal

import psycopg
import requests
import streamlit as st
from psycopg.rows import dict_row


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="AI Invoice Auditor",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATABASE_URL = os.getenv("DATABASE_URL", "")
AGENT_API_URL = os.getenv(
    "AGENT_API_URL", "http://localhost:8000"
).rstrip("/")
API_TIMEOUT = 60


# ---------------------------------------------------------
# DATABASE HELPERS
# ---------------------------------------------------------

def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=5,
    )


def fetch_all(query, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def fetch_one(query, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()


def get_invoices():
    return fetch_all("""
        SELECT
            invoice_id,
            file_path,
            invoice_number,
            vendor_id,
            vendor_name,
            po_number,
            invoice_date,
            currency,
            total_amount,
            validation_status,
            recommendation,
            source_language,
            translation_confidence,
            raw_extracted_text,
            translated_text,
            extracted_raw,
            processed_at
        FROM audit.invoice_audit
        ORDER BY processed_at DESC NULLS LAST
    """)


def get_invoice(invoice_id):
    return fetch_one("""
        SELECT *
        FROM audit.invoice_audit
        WHERE invoice_id = %s
    """, (invoice_id,))


def get_line_items(invoice_id):
    return fetch_all("""
        SELECT
            id,
            line_number,
            item_code,
            description,
            quantity,
            unit_price,
            line_total
        FROM audit.invoice_line_items
        WHERE invoice_id = %s
        ORDER BY line_number NULLS LAST, id
    """, (invoice_id,))


def get_discrepancies(invoice_id=None):
    query = """
        SELECT
            id,
            invoice_id,
            field_name,
            invoice_value,
            erp_value,
            deviation_pct,
            severity,
            detected_at
        FROM audit.discrepancies
    """
    params = ()

    if invoice_id:
        query += " WHERE invoice_id = %s"
        params = (invoice_id,)

    query += " ORDER BY detected_at DESC NULLS LAST"
    return fetch_all(query, params)


def get_feedback(invoice_id=None):
    query = """
        SELECT
            id,
            invoice_id,
            field_name,
            original_value,
            corrected_value,
            corrected_by,
            corrected_at,
            revalidated
        FROM audit.human_feedback
    """
    params = ()

    if invoice_id:
        query += " WHERE invoice_id = %s"
        params = (invoice_id,)

    query += " ORDER BY corrected_at DESC NULLS LAST"
    return fetch_all(query, params)


# ---------------------------------------------------------
# AGENT API HELPERS
# ---------------------------------------------------------

def agent_post(path, payload=None, files=None, data=None):
    response = requests.post(
        f"{AGENT_API_URL}{path}",
        json=payload,
        files=files,
        data=data,
        timeout=API_TIMEOUT,
    )
    response.raise_for_status()

    if response.content:
        return response.json()
    return {}


def show_api_error(exc):
    if isinstance(exc, requests.HTTPError):
        detail = exc.response.text[:1000] if exc.response else str(exc)
        st.error(f"Agent API error: {detail}")
    elif isinstance(exc, requests.RequestException):
        st.error(f"Cannot connect to the Agent API: {exc}")
    else:
        st.error(str(exc))


# ---------------------------------------------------------
# DISPLAY HELPERS
# ---------------------------------------------------------

def money(value, currency=None):
    if value is None:
        return "—"
    prefix = f"{currency} " if currency else ""
    return f"{prefix}{float(value):,.2f}"


def recommendation_label(value):
    labels = {
        "approve": "Approve",
        "manual_review": "Manual review",
        "review": "Manual review",
        "reject": "Reject",
    }
    return labels.get(value or "", value or "Pending")


def validation_label(value):
    labels = {
        "passed": "Passed",
        "partial": "Partial",
        "failed": "Failed",
    }
    return labels.get(value or "", value or "Pending")


def show_json(value):
    if value is None:
        st.info("No data available.")
    elif isinstance(value, (dict, list)):
        st.json(value)
    else:
        st.code(str(value))


# ---------------------------------------------------------
# PAGE STYLING
# ---------------------------------------------------------

st.markdown("""
<style>
.block-container {
    padding-top: 1.5rem;
    max-width: 1500px;
}
.app-subtitle {
    color: #6b7280;
    margin-top: -8px;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------

with st.sidebar:
    st.title("🧾 AI Invoice Auditor")
    st.caption("Human-in-the-Loop Invoice Validation")
    st.divider()

    page = st.radio(
        "Navigation",
        [
            "📊 Dashboard",
            "📥 Incoming Invoices",
            "📄 Invoice Review",
            "⚠️ Discrepancies",
            "✏️ Correction & Revalidation",
            "🤖 RAG Chat",
            "💬 Feedback",
        ],
    )

    if st.button("🔄 Refresh data", use_container_width=True):
        st.rerun()


# ---------------------------------------------------------
# LOAD REAL DATABASE DATA
# ---------------------------------------------------------

try:
    invoices = get_invoices()
    db_error = None
except Exception as exc:
    invoices = []
    db_error = exc

if db_error:
    st.error(
        "Could not load invoices from PostgreSQL. "
        "Check DATABASE_URL, database availability, and the audit schema."
    )
    st.code(str(db_error))
    st.stop()


invoice_ids = [str(row["invoice_id"]) for row in invoices]
invoice_by_id = {
    str(row["invoice_id"]): row for row in invoices
}


# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------

if page == "📊 Dashboard":
    st.title("AI Invoice Auditor")
    st.markdown(
        '<p class="app-subtitle">Invoice processing, validation, '
        'and human review dashboard</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    review_count = sum(
        row.get("recommendation") in ("manual_review", "review")
        for row in invoices
    )
    passed_count = sum(
        row.get("validation_status") == "passed"
        for row in invoices
    )
    failed_count = sum(
        row.get("validation_status") == "failed"
        for row in invoices
    )

    try:
        discrepancy_count = fetch_one(
            "SELECT COUNT(*) AS count FROM audit.discrepancies"
        )["count"]
    except Exception:
        discrepancy_count = "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Invoices", len(invoices))
    c2.metric("Pending Review", review_count)
    c3.metric("Passed Validation", passed_count)
    c4.metric("Discrepancies", discrepancy_count)

    st.subheader("Recent Invoices")

    if invoices:
        rows = []
        for invoice in invoices:
            rows.append({
                "Invoice ID": str(invoice["invoice_id"]),
                "Invoice Number": invoice.get("invoice_number") or "—",
                "Vendor": invoice.get("vendor_name") or "—",
                "Date": str(invoice.get("invoice_date") or "—"),
                "Amount": money(
                    invoice.get("total_amount"),
                    invoice.get("currency"),
                ),
                "Validation": validation_label(
                    invoice.get("validation_status")
                ),
                "Recommendation": recommendation_label(
                    invoice.get("recommendation")
                ),
            })

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No invoices have been recorded yet.")


# ---------------------------------------------------------
# INCOMING INVOICES
# ---------------------------------------------------------

elif page == "📥 Incoming Invoices":
    st.title("📥 Incoming Invoices")
    st.write(
        "Upload a PDF, DOCX, or image. The Agent API should save "
        "the file into the monitored incoming directory."
    )

    uploaded_file = st.file_uploader(
        "Choose invoice",
        type=["pdf", "docx", "png", "jpg", "jpeg"],
    )

    if uploaded_file and st.button(
        "Submit Invoice for Processing",
        type="primary",
    ):
        try:
            result = agent_post(
                "/api/invoices/upload",
                files={
                    "file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        uploaded_file.type or "application/octet-stream",
                    )
                },
            )
            st.success("Upload request completed.")
            show_json(result)
            st.info(
                "Refresh the dashboard after processing finishes "
                "to see the saved audit record."
            )
        except Exception as exc:
            show_api_error(exc)

    st.divider()
    st.subheader("Recorded Invoices")

    if invoices:
        st.dataframe(
            [
                {
                    "Invoice ID": str(row["invoice_id"]),
                    "File": row.get("file_path") or "—",
                    "Status": validation_label(
                        row.get("validation_status")
                    ),
                    "Processed": str(row.get("processed_at") or "—"),
                }
                for row in invoices
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No invoice records found.")


# ---------------------------------------------------------
# INVOICE REVIEW
# ---------------------------------------------------------

elif page == "📄 Invoice Review":
    st.title("📄 Invoice Review")

    if not invoice_ids:
        st.info("No invoices available to review.")
    else:
        selected = st.selectbox("Select invoice", invoice_ids)
        invoice = invoice_by_id[selected]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Invoice Number", invoice.get("invoice_number") or "—")
        c2.metric("Vendor", invoice.get("vendor_name") or "—")
        c3.metric(
            "Total Amount",
            money(invoice.get("total_amount"), invoice.get("currency")),
        )
        c4.metric(
            "Recommendation",
            recommendation_label(invoice.get("recommendation")),
        )

        st.caption(f"Invoice ID: {selected}")
        st.caption(
            f"Validation: {validation_label(invoice.get('validation_status'))}"
        )

        st.subheader("Extracted Header")
        st.dataframe(
            [{
                "Invoice Number": invoice.get("invoice_number"),
                "Vendor ID": invoice.get("vendor_id"),
                "Vendor": invoice.get("vendor_name"),
                "PO Number": invoice.get("po_number"),
                "Invoice Date": str(invoice.get("invoice_date") or ""),
                "Currency": invoice.get("currency"),
                "Total": invoice.get("total_amount"),
                "Source Language": invoice.get("source_language"),
                "Translation Confidence": invoice.get("translation_confidence"),
            }],
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Line Items")
        try:
            line_items = get_line_items(selected)
            if line_items:
                st.dataframe(
                    [
                        {
                            "Line": item.get("line_number"),
                            "Item Code": item.get("item_code"),
                            "Description": item.get("description"),
                            "Quantity": item.get("quantity"),
                            "Unit Price": item.get("unit_price"),
                            "Line Total": item.get("line_total"),
                        }
                        for item in line_items
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No line items recorded.")
        except Exception as exc:
            st.warning(f"Could not load line items: {exc}")

        with st.expander("Raw extracted text"):
            st.text_area(
                "Original extracted text",
                value=invoice.get("raw_extracted_text") or "",
                height=220,
                disabled=True,
            )

        with st.expander("Translated text"):
            st.text_area(
                "English translation",
                value=invoice.get("translated_text") or "",
                height=220,
                disabled=True,
            )

        with st.expander("Structured extraction"):
            show_json(invoice.get("extracted_raw"))


# ---------------------------------------------------------
# DISCREPANCIES
# ---------------------------------------------------------

elif page == "⚠️ Discrepancies":
    st.title("⚠️ Discrepancies")

    selected = None
    if invoice_ids:
        selected = st.selectbox(
            "Filter by invoice",
            ["All invoices"] + invoice_ids,
        )

    try:
        discrepancies = get_discrepancies(
            None if selected in (None, "All invoices") else selected
        )

        if not discrepancies:
            st.success("No recorded discrepancies.")
        else:
            st.dataframe(
                [
                    {
                        "Invoice ID": str(row["invoice_id"]),
                        "Field": row.get("field_name"),
                        "Invoice Value": row.get("invoice_value"),
                        "ERP Value": row.get("erp_value"),
                        "Deviation %": row.get("deviation_pct"),
                        "Severity": row.get("severity"),
                        "Detected": str(row.get("detected_at") or ""),
                    }
                    for row in discrepancies
                ],
                use_container_width=True,
                hide_index=True,
            )
    except Exception as exc:
        st.error(f"Could not load discrepancies: {exc}")


# ---------------------------------------------------------
# CORRECTION & REVALIDATION
# ---------------------------------------------------------

elif page == "✏️ Correction & Revalidation":
    st.title("✏️ Correction & Revalidation")

    st.info(
        "Corrections should be saved as human feedback. "
        "The original extracted value must remain unchanged."
    )

    if not invoice_ids:
        st.info("No invoices available.")
    else:
        selected = st.selectbox("Select invoice", invoice_ids)
        invoice = invoice_by_id[selected]

        fields = {
            "invoice_number": invoice.get("invoice_number"),
            "vendor_id": invoice.get("vendor_id"),
            "vendor_name": invoice.get("vendor_name"),
            "po_number": invoice.get("po_number"),
            "invoice_date": str(invoice.get("invoice_date") or ""),
            "currency": invoice.get("currency"),
            "total_amount": (
                str(invoice.get("total_amount"))
                if invoice.get("total_amount") is not None
                else ""
            ),
        }

        with st.form("correction_form"):
            field_name = st.selectbox(
                "Field to correct",
                list(fields.keys()),
            )
            original_value = fields[field_name]
            st.text_input(
                "Original value",
                value="" if original_value is None else str(original_value),
                disabled=True,
            )
            corrected_value = st.text_input("Corrected value")
            corrected_by = st.text_input("Auditor")
            reason = st.text_area("Reason for correction")
            save = st.form_submit_button("Save Correction")

        if save:
            if not corrected_by.strip() or not reason.strip():
                st.warning("Enter the auditor and reason.")
            elif corrected_value.strip() == "":
                st.warning("Enter a corrected value.")
            else:
                try:
                    result = agent_post(
                        f"/api/invoices/{selected}/feedback",
                        payload={
                            "field_name": field_name,
                            "original_value": (
                                None if original_value is None
                                else str(original_value)
                            ),
                            "corrected_value": corrected_value.strip(),
                            "corrected_by": corrected_by.strip(),
                            "comments": reason.strip(),
                        },
                    )
                    st.success("Correction submitted.")
                    show_json(result)
                except Exception as exc:
                    show_api_error(exc)

        st.divider()

        if st.button("Revalidate Invoice", type="primary"):
            try:
                result = agent_post(
                    f"/api/invoices/{selected}/revalidate",
                    payload={},
                )
                st.success("Revalidation request completed.")
                show_json(result)
            except Exception as exc:
                show_api_error(exc)

        st.subheader("Correction History")
        try:
            feedback_rows = get_feedback(selected)
            if feedback_rows:
                st.dataframe(
                    [
                        {
                            "Field": row.get("field_name"),
                            "Original": row.get("original_value"),
                            "Corrected": row.get("corrected_value"),
                            "Auditor": row.get("corrected_by"),
                            "Date": str(row.get("corrected_at") or ""),
                            "Revalidated": row.get("revalidated"),
                        }
                        for row in feedback_rows
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No feedback recorded for this invoice.")
        except Exception as exc:
            st.warning(f"Could not load feedback: {exc}")


# ---------------------------------------------------------
# RAG CHAT
# ---------------------------------------------------------

elif page == "🤖 RAG Chat":
    st.title("🤖 Invoice RAG Assistant")
    st.write(
        "Ask questions about processed invoices and their audit reports."
    )

    selected = st.selectbox(
        "Invoice context",
        ["All invoices"] + invoice_ids,
    )

    question = st.text_area(
        "Your question",
        placeholder=(
            "Why was this invoice flagged? "
            "Which PO line has a price discrepancy?"
        ),
    )

    if st.button("Ask AI", type="primary"):
        if not question.strip():
            st.warning("Enter a question.")
        else:
            try:
                result = agent_post(
                    "/api/query",
                    payload={
                        "question": question.strip(),
                        "invoice_id": (
                            None if selected == "All invoices"
                            else selected
                        ),
                    },
                )

                st.subheader("Answer")
                st.write(result.get("answer", "No answer returned."))

                if result.get("score") is not None:
                    st.metric("Confidence Score", result["score"])

                with st.expander("Retrieved context and details"):
                    show_json(result)
            except Exception as exc:
                show_api_error(exc)


# ---------------------------------------------------------
# FEEDBACK
# ---------------------------------------------------------

elif page == "💬 Feedback":
    st.title("💬 Auditor Feedback")

    if not invoice_ids:
        st.info("No invoices available.")
    else:
        selected = st.selectbox("Invoice", invoice_ids)

        feedback_type = st.selectbox(
            "Feedback type",
            ["Correction", "Validation", "RAG Answer", "Other"],
        )
        comments = st.text_area("Feedback")
        submitted_by = st.text_input("Auditor")

        if st.button("Submit Feedback"):
            if not comments.strip():
                st.warning("Please enter feedback.")
            elif not submitted_by.strip():
                st.warning("Please enter the auditor.")
            else:
                try:
                    result = agent_post(
                        f"/api/invoices/{selected}/feedback",
                        payload={
                            "field_name": "general_feedback",
                            "original_value": None,
                            "corrected_value": None,
                            "corrected_by": submitted_by.strip(),
                            "comments": (
                                f"Type: {feedback_type}\n"
                                f"{comments.strip()}"
                            ),
                        },
                    )
                    st.success("Feedback submitted to the Agent API.")
                    show_json(result)
                except Exception as exc:
                    show_api_error(exc)

    st.divider()
    st.subheader("Recorded Feedback")

    try:
        all_feedback = get_feedback()
        if all_feedback:
            st.dataframe(
                [
                    {
                        "Invoice ID": str(row["invoice_id"]),
                        "Field": row.get("field_name"),
                        "Original": row.get("original_value"),
                        "Corrected": row.get("corrected_value"),
                        "Auditor": row.get("corrected_by"),
                        "Date": str(row.get("corrected_at") or ""),
                        "Revalidated": row.get("revalidated"),
                    }
                    for row in all_feedback
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No feedback records found.")
    except Exception as exc:
        st.warning(f"Could not load feedback: {exc}")

