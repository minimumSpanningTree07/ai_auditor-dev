import streamlit as st
from datetime import datetime


# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------

st.set_page_config(
    page_title="AI Invoice Auditor",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)
# ---------------------------------------------------------
# SAMPLE DATA
# ---------------------------------------------------------

if "invoices" not in st.session_state:
    st.session_state.invoices = [
        {
            "invoice_id": "INV-004",
            "vendor": "ABC Technologies",
            "date": "2026-10-13",
            "amount": 2450.00,
            "status": "Review",
            "discrepancies": 2
        },
        {
            "invoice_id": "INV-003",
            "vendor": "Global Supplies",
            "date": "2026-10-12",
            "amount": 1200.00,
            "status": "Passed",
            "discrepancies": 0
        },
        {
            "invoice_id": "INV-002",
            "vendor": "Metro Office Solutions",
            "date": "2026-10-11",
            "amount": 3100.00,
            "status": "Failed",
            "discrepancies": 3
        },
        {
            "invoice_id": "INV-001",
            "vendor": "TechSource Pvt Ltd",
            "date": "2026-10-10",
            "amount": 1500.00,
            "status": "Passed",
            "discrepancies": 0
        }
    ]

if "feedback" not in st.session_state:
    st.session_state.feedback = []


# ---------------------------------------------------------
# CSS
# ---------------------------------------------------------

st.markdown("""
<style>

.main {
    background-color: #f7f9fc;
}

.block-container {
    padding-top: 2rem;
    padding-left: 3rem;
    padding-right: 3rem;
    max-width: 1400px;
}

.app-title {
    font-size: 28px;
    font-weight: 700;
    color: #17365D;
    line-height: 1.2;
    margin: 0;
    padding: 0;
    white-space:nowrap;
}
.app-subtitle {
    color: #6b7280;
    font-size: 14px;
    margin-top: 6px;
    margin-bottom: 10px;
}

.card {
    background-color: white;
    padding: 20px;
    border-radius: 10px;
    border: 1px solid #e5e7eb;
    margin-bottom: 15px;
}

.metric-title {
    color: #6b7280;
    font-size: 14px;
}

.metric-value {
    color: #17365D;
    font-size: 28px;
    font-weight: 700;
}

.section-title {
    font-size: 20px;
    font-weight: 600;
    color: #17365D;
    margin-top: 10px;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------

with st.sidebar:

    st.markdown("## 🧾 AI Invoice Auditor")

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
            "💬 Feedback"
        ]
    )

    st.divider()

    # ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------

if page == "📊 Dashboard":

    st.markdown(
        '<div class="app-title">AI Invoice Auditor</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="app-subtitle">'
        'Invoice validation and human review dashboard'
        '</div>',
        unsafe_allow_html=True
    )

    st.divider()

    total = len(st.session_state.invoices)

    review = sum(
        1 for x in st.session_state.invoices
        if x["status"] == "Review"
    )
    passed = sum(
        1 for x in st.session_state.invoices
        if x["status"] == "Passed"
    )

    issues = sum(
        x["discrepancies"] for x in st.session_state.invoices
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Total Invoices", total)

    with c2:
        st.metric("Pending Review", review)

    with c3:
        st.metric("Passed", passed)

    with c4:
        st.metric("Discrepancies", issues)

    st.markdown("### Recent / Incoming Invoices")
    for invoice in st.session_state.invoices:

        with st.container(border=True):

            c1, c2, c3, c4, c5 = st.columns(
                [1.2, 2, 1.3, 1.2, 1]
            )

            c1.write(f"**{invoice['invoice_id']}**")
            c2.write(invoice["vendor"])
            c3.write(f"${invoice['amount']:,.2f}")
            c4.write(invoice["status"])
            c5.write(
                f"{invoice['discrepancies']} issue(s)"
            )
# ---------------------------------------------------------
# INCOMING INVOICES
# ---------------------------------------------------------

elif page == "📥 Incoming Invoices":

    st.markdown("## 📥 Incoming Invoices")

    st.write(
        "Upload a new invoice for processing. "
        "Backend processing will be connected later."
    )

    uploaded_file = st.file_uploader(
        "Add new invoice",
        type=["pdf", "png", "jpg", "jpeg", "docx"]
    )

    if uploaded_file:

        st.success(
            f"Invoice selected: {uploaded_file.name}"
        )

        if st.button("➕ Add to Incoming Queue"):

            new_id = f"NEW-{len(st.session_state.invoices) + 1:03d}"

            new_invoice = {
                "invoice_id": new_id,
                "vendor": "Pending Extraction",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "amount": 0.00,
                "status": "Pending",
                "discrepancies": 0
            }

            # New invoice appears first
            st.session_state.invoices.insert(
                0,
                new_invoice
            )

            st.success(
                f"{new_id} added to incoming invoices."
            )

            st.rerun()

    st.divider()
    st.markdown("### Incoming Queue")

    for invoice in st.session_state.invoices:

        if invoice["status"] == "Pending":

            st.info(
                f"**{invoice['invoice_id']}**  |  "
                f"{invoice['vendor']}  |  "
                f"{invoice['date']}"
            )
# ---------------------------------------------------------
# INVOICE REVIEW
# ---------------------------------------------------------

elif page == "📄 Invoice Review":

    st.markdown("## 📄 Invoice Review")

    invoice_ids = [
        x["invoice_id"]
        for x in st.session_state.invoices
    ]

    selected = st.selectbox(
        "Select Invoice",
        invoice_ids
    )

    invoice = next(
        x for x in st.session_state.invoices
        if x["invoice_id"] == selected
    )

    st.markdown("### Invoice Summary")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Invoice ID", invoice["invoice_id"])
    c2.metric("Vendor", invoice["vendor"])
    c3.metric("Amount", f"${invoice['amount']:,.2f}")
    c4.metric("Status", invoice["status"])
    st.divider()

    st.markdown("### Extracted Values")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input(
            "Invoice Number",
            value=invoice["invoice_id"]
        )

        st.text_input(
            "Vendor",
            value=invoice["vendor"]
        )

    with col2:
        st.text_input(
            "Invoice Date",
            value=invoice["date"]
        )

        st.number_input(
            "Total Amount",
            value=float(invoice["amount"])
        )

    st.markdown("### Invoice Report")

    st.text_area(
        "Report",
        value=(
            "Invoice extraction and validation report "
            "will appear here."
        ),
        height=180
    )
# ---------------------------------------------------------
# DISCREPANCIES
# ---------------------------------------------------------

elif page == "⚠️ Discrepancies":

    st.markdown("## ⚠️ Discrepancies")

    invoice_ids = [
        x["invoice_id"]
        for x in st.session_state.invoices
        if x["discrepancies"] > 0
    ]

    if not invoice_ids:

        st.success("No discrepancies found.")

    else:

        selected = st.selectbox(
            "Select Invoice",
            invoice_ids
        )

        invoice = next(
            x for x in st.session_state.invoices
            if x["invoice_id"] == selected
        )

        st.warning(
            f"{invoice['discrepancies']} discrepancy(ies) "
            f"found for {invoice['invoice_id']}"
        )

        st.markdown("### Discrepancy Details")

        st.dataframe(
            [
                {
                    "Field": "Total Amount",
                    "Extracted": "$2,450.00",
                    "Expected": "$2,400.00",
                    "Status": "Mismatch"
                },
                {
                    "Field": "Invoice Date",
                    "Extracted": "2026-10-13",
                    "Expected": "2026-10-12",
                    "Status": "Mismatch"
                }
            ],
            use_container_width=True,
            hide_index=True
        )
# ---------------------------------------------------------
# CORRECTION & REVALIDATION
# ---------------------------------------------------------

elif page == "✏️ Correction & Revalidation":

    st.markdown("## ✏️ Correction & Revalidation")

    st.info(
        "Corrections will be recorded as human feedback. "
        "The original extracted value will remain unchanged."
    )

    invoice_ids = [
        x["invoice_id"]
        for x in st.session_state.invoices
    ]

    selected = st.selectbox(
        "Select Invoice",
        invoice_ids
    )

    invoice = next(
        x for x in st.session_state.invoices
        if x["invoice_id"] == selected
    )

    st.markdown("### Correct Extracted Values")

    corrected_vendor = st.text_input(
        "Vendor",
        value=invoice["vendor"]
    )

    corrected_amount = st.number_input(
        "Total Amount",
        value=float(invoice["amount"])
    )

    reason = st.text_area(
        "Reason for correction"
    )

    if st.button("Save Correction"):

        st.success(
            "Correction recorded successfully."
        )

        st.info(
            "Revalidation will be connected to the Agent API later."
        )

    if st.button("Revalidate"):

        st.info(
            "Revalidation API will be called here."
        )
# ---------------------------------------------------------
# RAG CHAT
# ---------------------------------------------------------

elif page == "🤖 RAG Chat":

    st.markdown("## 🤖 Invoice RAG Assistant")

    st.write(
        "Ask natural-language questions about processed invoices."
    )

    invoice_ids = [
        x["invoice_id"]
        for x in st.session_state.invoices
    ]

    selected = st.selectbox(
        "Invoice",
        invoice_ids
    )

    question = st.text_input(
        "Ask a question",
        placeholder="What is the total amount due?"
    )

    if st.button("Ask AI"):

        if question:

            st.markdown("### AI Answer")

            st.info(
                "The RAG response will appear here "
                "after the /query API is connected."
            )

            st.caption(
                f"Invoice: {selected}"
            )

        else:

            st.warning("Please enter a question.")
# ---------------------------------------------------------
# FEEDBACK
# ---------------------------------------------------------

elif page == "💬 Feedback":

    st.markdown("## 💬 Auditor Feedback")

    invoice_ids = [
        x["invoice_id"]
        for x in st.session_state.invoices
    ]

    selected = st.selectbox(
        "Invoice",
        invoice_ids
    )

    feedback_type = st.selectbox(
        "Feedback Type",
        [
            "Correction",
            "Validation",
            "RAG Answer",
            "Other"
        ]
    )

    feedback = st.text_area(
        "Feedback"
    )

    if st.button("Submit Feedback"):

        if feedback:

            st.session_state.feedback.append(
                {
                    "invoice_id": selected,
                    "type": feedback_type,
                    "feedback": feedback,
                    "time": datetime.now().strftime(
                        "%Y-%m-%d %H:%M"
                    )
                }
            )

            st.success(
                "Feedback recorded."
            )

        else:

            st.warning(
                "Please enter feedback."
            )



