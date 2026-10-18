from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from api_client import (
    AgentAPIError, health, get_dashboard_summary, get_invoices,
    get_upload_status, get_invoice, upload_invoice, revalidate_invoice, ask_ai,
    clear_pending_queue, reset_invoice_workspace, get_erp_purchase_order, save_human_feedback,
)

st.set_page_config(
    page_title="AI Invoice Auditor",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
:root { --ink:#182a32; --muted:#66777b; --line:#dce5e2; --brand:#176b63; --brand-soft:#eaf5f2; --canvas:#f4f7f5; }
.stApp { background:var(--canvas); color:var(--ink); }
[data-testid="stAppViewContainer"] .main p, [data-testid="stAppViewContainer"] .main h1, [data-testid="stAppViewContainer"] .main h2, [data-testid="stAppViewContainer"] .main h3, [data-testid="stAppViewContainer"] .main h4, [data-testid="stAppViewContainer"] .main label, [data-testid="stAppViewContainer"] .main li, [data-testid="stAppViewContainer"] .main [data-testid="stMarkdownContainer"] { color:var(--ink); }
[data-testid="stAppViewContainer"] .main .stButton button { color:var(--ink); }
[data-testid="stAppViewContainer"] .main input,
[data-testid="stAppViewContainer"] .main textarea,
[data-testid="stAppViewContainer"] .main [data-baseweb="select"] input {
  background-color:#ffffff !important; color:#182a32 !important; -webkit-text-fill-color:#182a32 !important;
}
[data-testid="stAppViewContainer"] .main .stButton button[kind="primary"] { color:#ffffff; }
[data-testid="stAppViewContainer"] .main [data-testid="stMetricValue"] { color:#14243a; }
[data-testid="stAppViewContainer"] .main [data-testid="stMetricLabel"] { color:#52656b; }
[data-testid="stHeader"] { background:rgba(246,248,252,.92); }
.block-container { padding-top:1.35rem; padding-bottom:3rem; max-width:1500px; }
[data-testid="stSidebar"] { background:#172d35; }
[data-testid="stSidebar"] * { color:#edf3ff !important; }
[data-testid="stSidebar"] [data-testid="stRadio"] label { padding:.48rem .65rem; border-radius:10px; }
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background:#25444b; }
[data-testid="stMetric"] { background:#fff; border:1px solid var(--line); padding:1rem 1.1rem; border-radius:16px; box-shadow:0 2px 8px rgba(24,39,75,.035); }
[data-testid="stMetricLabel"] { color:var(--muted); font-weight:600; }
[data-testid="stMetricValue"] { color:var(--ink); }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius:16px; border-color:var(--line); background:#fff; }
.stButton > button { border-radius:10px; min-height:2.55rem; font-weight:600; }
.stButton > button[kind="primary"] { background:#176b63; border-color:#176b63; }
/* Force readable form controls in both light and dark browser themes. */
.stTextInput input, .stTextArea textarea, .stNumberInput input,
[data-testid="stDateInput"] input, [data-testid="stTimeInput"] input,
[data-baseweb="select"] > div, [data-baseweb="input"] > div,
[data-baseweb="textarea"] > div {
  border-radius:10px !important; background:#ffffff !important; color:#182a32 !important;
  border-color:#cbd8d5 !important; caret-color:#176b63 !important; opacity:1 !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder,
.stNumberInput input::placeholder { color:#66777b !important; opacity:1 !important; }
[data-baseweb="select"] input, [data-baseweb="select"] span,
[data-baseweb="select"] div, [data-baseweb="popover"] *,
[role="listbox"] *, [role="option"] { color:#182a32; }
[data-baseweb="popover"] [role="listbox"], [role="listbox"] { background:#ffffff !important; }
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
  border-color:#176b63 !important; box-shadow:0 0 0 1px #176b63 !important;
}
[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:12px; overflow:hidden; }
hr { border-color:var(--line); }
.eyebrow { color:#287b70; text-transform:uppercase; letter-spacing:.12em; font-size:.72rem; font-weight:800; margin-bottom:.25rem; }
.page-title { color:#14243a; font-size:2rem; font-weight:800; letter-spacing:-.035em; margin:0; line-height:1.15; }
.page-subtitle { color:#64748b; margin-top:.45rem; margin-bottom:1.35rem; font-size:.98rem; }
.hero { background:linear-gradient(120deg,#17343b,#176b63); color:white; padding:1.5rem 1.7rem; border-radius:18px; margin-bottom:1.15rem; box-shadow:0 12px 28px rgba(30,64,120,.14); }
.hero h2 { color:#ffffff !important; margin:0; font-size:1.5rem; }
.hero p { color:#e0f2ef !important; margin:.45rem 0 0; }
.soft-note { background:#eaf5f2; border:1px solid #d4e8e2; padding:.85rem 1rem; border-radius:12px; color:#22554e; }
.stage-done { color:#176b63; font-weight:700; }
.stage-wait { color:#64748b; }
.answer-box { background:#fff; border:1px solid #dfe7f2; border-left:4px solid #176b63; padding:1.2rem 1.35rem; border-radius:14px; line-height:1.7; }
.file-chip { display:inline-block; padding:.28rem .55rem; background:#eef4ff; color:#2858a6; border-radius:7px; font-size:.8rem; font-weight:700; }
.small-muted { color:#64748b; font-size:.86rem; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str, eyebrow: str = "WORKSPACE") -> None:
    st.markdown(
        f'<div class="eyebrow">{eyebrow}</div><h1 class="page-title">{title}</h1>'
        f'<div class="page-subtitle">{subtitle}</div>',
        unsafe_allow_html=True,
    )


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None and str(value).strip() else default
    except (TypeError, ValueError):
        return default


def status_label(value: Any) -> str:
    value = str(value or "unknown").replace("_", " ").strip()
    return value.title()


def _navigate_to(page: str) -> None:
    st.session_state["main_navigation"] = page


def main() -> None:
    with st.sidebar:
        st.markdown("<div style='font-size:2rem'>🧾</div><div style='font-size:1.1rem;font-weight:800'>Invoice Auditor</div><div style='font-size:.78rem;color:#a9bddb'>AI-powered control room</div>", unsafe_allow_html=True)
        st.divider()
        page = st.radio(
            "WORKSPACE",
            ["Dashboard", "Invoices & Review", "Human Review", "Upload Center", "Ask AI"],
            label_visibility="visible",
            key="main_navigation",
        )
        st.divider()
        try:
            health_result = health()
            st.markdown("**System health**")
            if health_result.get("status") == "healthy":
                st.success("Services online")
            else:
                st.warning("Some services need attention")
            # Keep the sidebar compact; detailed dependency health belongs in a
            # dedicated diagnostics view, not beside primary navigation.
        except AgentAPIError:
            st.error("Agent API offline")
            st.caption("Start the Compose services and refresh.")
        st.markdown("<div style='margin-top:2rem;font-size:.72rem;color:#8fa6c6'>LOCAL WORKSPACE · DOCKER COMPOSE</div>", unsafe_allow_html=True)

    if page == "Dashboard":
        dashboard_page()
    elif page == "Invoices & Review":
        invoices_page()
    elif page == "Human Review":
        human_review_page()
    elif page == "Upload Center":
        upload_page()
    else:
        ask_ai_page()


def dashboard_page() -> None:
    page_header("Invoice control room", "A clear view of processing, audit outcomes and items that need your attention.", "OVERVIEW")
    try:
        summary = get_dashboard_summary()
        invoices = get_invoices()
        uploads = get_upload_status().get("files", [])
    except AgentAPIError as exc:
        st.error(f"Could not load dashboard data: {exc}")
        return

    st.markdown('<div class="hero"><h2>Welcome to your audit workspace</h2><p>Track incoming invoices, understand exceptions and move each invoice from upload to a verified decision.</p></div>', unsafe_allow_html=True)
    metrics = st.columns(4)
    metric_values = [
        ("Total invoices", summary.get("total_invoices", len(invoices)), "Records saved in audit database"),
        ("Approved", summary.get("approved_invoices", summary.get("approved", 0)), "Passed audit recommendation"),
        ("Needs review", summary.get("review_invoices", summary.get("manual_review", 0)), "Requires an auditor decision"),
        ("Open discrepancies", summary.get("open_discrepancies", summary.get("total_discrepancies", 0)), "Exceptions not yet resolved"),
    ]
    for col, (label, value, help_text) in zip(metrics, metric_values):
        col.metric(label, value or 0, help=help_text)

    st.write("")
    left, right = st.columns([1.35, 1])
    with left, st.container(border=True):
        st.subheader("Recent invoice activity")
        if invoices:
            rows = []
            for item in invoices[:8]:
                rows.append({
                    "File": item.get("file_name") or "Unknown file",
                    "Invoice no.": item.get("invoice_number") or "Pending extraction",
                    "Vendor": item.get("vendor_name") or "Unknown vendor",
                    "Total": f"{item.get('currency') or ''} {item.get('total_amount') if item.get('total_amount') is not None else '—'}".strip(),
                    "Status": status_label(item.get("validation_status")),
                    "Decision": status_label(item.get("recommendation")),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No invoices have been saved yet. Upload a file to begin.")
        st.button("Open invoice review", type="primary", use_container_width=True,
                  on_click=_navigate_to, args=("Invoices & Review",))
    with right, st.container(border=True):
        st.subheader("Incoming file queue")
        if uploads:
            counts: dict[str, int] = {}
            for item in uploads:
                key = status_label(item.get("status"))
                counts[key] = counts.get(key, 0) + 1
            for label, count in sorted(counts.items()):
                c1, c2 = st.columns([3, 1])
                c1.write(label)
                c2.metric("Files", count, label_visibility="collapsed")
            st.caption("Files already present in data/incoming are discovered by the background watcher and may start processing automatically.")
        else:
            st.success("No files are waiting in the incoming queue.")
        st.button("Open upload center", use_container_width=True,
                  on_click=_navigate_to, args=("Upload Center",))

    st.write("")
    with st.container(border=True):
        st.subheader("Attention required")
        needs_review = [x for x in invoices if str(x.get("validation_status") or "").lower() in {"manual_review", "pending_review", "rejected"}]
        if needs_review:
            st.warning(f"{len(needs_review)} invoice(s) need review or follow-up.")
            st.dataframe(pd.DataFrame([{
                "File": x.get("file_name") or "Unknown file",
                "Invoice no.": x.get("invoice_number") or "Pending",
                "Vendor": x.get("vendor_name") or "Unknown",
                "Status": status_label(x.get("validation_status")),
                "Recommendation": status_label(x.get("recommendation")),
            } for x in needs_review[:10]]), use_container_width=True, hide_index=True)
        else:
            st.success("No invoices are currently flagged for manual review.")


def invoices_page() -> None:
    page_header("Invoices & human review", "Select a specific invoice to inspect its source, audit findings, line items and review history.", "AUDIT QUEUE")
    try:
        invoices = get_invoices()
        uploads = get_upload_status().get("files", [])
    except AgentAPIError as exc:
        st.error(f"Unable to load invoice data: {exc}")
        return

    if not invoices:
        st.info("No saved invoices are available yet. Upload an invoice, or check the incoming-file status below.")
        render_upload_status(uploads)
        return

    review_only = st.toggle("Show only invoices requiring human review", value=True, key="review_queue_only")
    search = st.text_input("Search invoices", placeholder="Search by filename, invoice number, vendor or PO…", key="invoice_search")
    filtered = []
    review_statuses = {"manual_review", "pending_review", "rejected", "failed"}
    for item in invoices:
        status_value = str(item.get("validation_status") or "").lower()
        needs_review = status_value in review_statuses or bool(item.get("human_review_required"))
        if review_only and not needs_review:
            continue
        haystack = " ".join(str(item.get(k) or "") for k in ("file_name", "invoice_number", "vendor_name", "po_number")).casefold()
        if search.casefold() in haystack:
            filtered.append(item)

    rows = [{
        "File name": x.get("file_name") or "Unknown file",
        "Invoice number": x.get("invoice_number") or "Pending extraction",
        "Vendor": x.get("vendor_name") or "Unknown vendor",
        "PO": x.get("po_number") or "—",
        "Date": str(x.get("invoice_date") or "—"),
        "Amount": f"{x.get('currency') or ''} {x.get('total_amount') if x.get('total_amount') is not None else '—'}".strip(),
        "Validation": status_label(x.get("validation_status")),
        "Recommendation": status_label(x.get("recommendation")),
    } for x in filtered]
    with st.container(border=True):
        st.subheader("Invoice register")
        st.caption(f"Showing {len(filtered)} invoice(s) from {len(invoices)} saved records. Choose a row to inspect extracted values and review findings.")
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No invoices match that search.")

    if not filtered:
        render_upload_status(uploads)
        return
    labels = {}
    for item in filtered:
        invoice_id = str(item.get("invoice_id") or "")
        label = f"{item.get('file_name') or 'Unknown file'}  ·  {item.get('invoice_number') or 'Number pending'}  ·  {item.get('vendor_name') or 'Vendor unknown'}  ·  {invoice_id[:8]}"
        labels[label] = invoice_id
    selected_label = st.selectbox("Select invoice to review", list(labels), key="invoice_detail_selection")
    selected_id = labels[selected_label]
    if not selected_id:
        st.warning("This invoice row has no saved invoice ID yet.")
        return
    try:
        invoice = get_invoice(selected_id)
    except AgentAPIError as exc:
        st.error(f"Could not load selected invoice: {exc}")
        return

    file_name = invoice.get("file_name") or "Unknown file"
    status = status_label(invoice.get("validation_status"))
    with st.container(border=True):
        st.markdown(f'<div class="eyebrow">SELECTED INVOICE</div><h2 style="margin:.1rem 0 .3rem;color:#14243a">{file_name}</h2><div class="small-muted">Invoice ID: {selected_id} · Invoice no.: {invoice.get("invoice_number") or "pending extraction"} · Vendor: {invoice.get("vendor_name") or "unknown"}</div>', unsafe_allow_html=True)
        m = st.columns(4)
        m[0].metric("Validation status", status)
        m[1].metric("Recommendation", status_label(invoice.get("recommendation")))
        m[2].metric("Invoice total", f"{invoice.get('currency') or ''} {invoice.get('total_amount') if invoice.get('total_amount') is not None else '—'}".strip())
        m[3].metric("Discrepancies", len(invoice.get("discrepancies") or []))
        if invoice.get("source_available") is False:
            st.error("Original source file is missing. Re-upload the same source file to restore it before revalidation. Saved audit history is preserved.")
        elif invoice.get("source_available") is True:
            st.success("Original source file is available. Revalidation can run against this file.")

    overview_tab, line_tab, discrepancy_tab, review_tab = st.tabs(["Overview", "Line items", "Discrepancies", "Human review"])
    with overview_tab:
        left, right = st.columns(2)
        with left, st.container(border=True):
            st.subheader("Invoice information")
            for label, key in [("Vendor", "vendor_name"), ("Invoice number", "invoice_number"), ("Purchase order", "po_number"), ("Invoice date", "invoice_date"), ("Currency", "currency")]:
                st.write(f"**{label}:** {invoice.get(key) or 'Not recorded'}")
        with right, st.container(border=True):
            st.subheader("Amounts")
            for label, key in [("Subtotal", "subtotal_amount"), ("Tax", "tax_amount"), ("Total", "total_amount")]:
                st.write(f"**{label}:** {invoice.get('currency') or ''} {invoice.get(key) if invoice.get(key) is not None else 'Not recorded'}".strip())
            st.write(f"**Tax rate:** {invoice.get('tax_rate') if invoice.get('tax_rate') is not None else 'Not recorded'}%")
            st.write(f"**Recommendation:** {status_label(invoice.get('recommendation'))}")
        with st.expander("Processing details", expanded=False):
            st.write(f"**Source available:** {'Yes' if invoice.get('source_available') else 'No'}")
            st.write(f"**File path:** {invoice.get('file_path') or 'Not recorded'}")
            st.write(f"**Updated:** {invoice.get('updated_at') or 'Not recorded'}")
            st.write(f"**Extraction method:** {invoice.get('extraction_method') or 'Not recorded'}")
    with line_tab:
        line_items = invoice.get("line_items") or []
        st.subheader(f"Extracted line items · {len(line_items)}")
        if line_items:
            st.dataframe(pd.DataFrame([{
                "Line": item.get("line_number", idx + 1), "SKU / item code": item.get("sku") or item.get("item_code") or "Unknown",
                "Description": item.get("description") or "—", "Quantity": item.get("quantity"),
                "Unit price": item.get("unit_price"), "Line total": item.get("line_total"),
                "Source": item.get("source") or "extraction",
            } for idx, item in enumerate(line_items)]), use_container_width=True, hide_index=True)
        else:
            st.info("No line items were saved for this invoice.")
    with discrepancy_tab:
        discrepancies = invoice.get("discrepancies") or []
        st.subheader(f"Audit findings · {len(discrepancies)}")
        if not discrepancies:
            st.success("No discrepancies are recorded for this invoice.")
        for idx, item in enumerate(discrepancies, start=1):
            severity = str(item.get("severity") or "info").upper()
            title = f"{idx}. {item.get('discrepancy_type') or 'Validation finding'} · {severity}"
            with st.expander(title, expanded=severity == "HIGH"):
                st.write(item.get("message") or "No explanation was saved.")
                if item.get("details"):
                    st.json(item["details"])
                st.caption(f"Finding status: {status_label(item.get('status'))}")
    with review_tab:
        render_hitl(invoice, selected_id)

    st.divider()
    render_upload_status(uploads, compact=True)



def human_review_page() -> None:
    """Dedicated, always-visible human review and correction workspace."""
    page_header(
        "Human review & corrections",
        "Compare the extracted invoice with the ERP purchase order, record feedback, then choose a revalidation or review action.",
        "AUDITOR WORKSPACE",
    )
    try:
        invoices = get_invoices()
    except AgentAPIError as exc:
        st.error(f"Unable to load invoices for review: {exc}")
        return

    review_statuses = {"manual_review", "pending_review", "rejected", "failed"}
    needs_review = [
        row for row in invoices
        if str(row.get("validation_status") or "").lower() in review_statuses
        or bool(row.get("human_review_required"))
    ]
    show_all = st.toggle("Show all invoices, including those not flagged for review", value=False, key="human_review_show_all")
    candidates = invoices if show_all else needs_review
    if not candidates:
        st.success("No invoices are currently flagged for human review.")
        if invoices:
            st.caption("Turn on ‘Show all invoices’ to open another invoice and optionally record feedback or rerun validation.")
        else:
            st.info("Upload an invoice first. Files in the incoming folder are processed by the background watcher.")
        return

    labels: dict[str, str] = {}
    for row in candidates:
        invoice_id = str(row.get("invoice_id") or "")
        if not invoice_id:
            continue
        label = (
            f"{row.get('file_name') or 'Unknown file'} · "
            f"{row.get('invoice_number') or 'Invoice number pending'} · "
            f"{row.get('vendor_name') or 'Vendor unknown'} · "
            f"{status_label(row.get('validation_status'))} · {invoice_id[:8]}"
        )
        labels[label] = invoice_id
    if not labels:
        st.warning("The review queue contains no saved invoice IDs yet.")
        return

    st.markdown("### Select invoice to review")
    selected_label = st.selectbox("Invoice requiring attention", list(labels), key="dedicated_human_review_invoice")
    invoice_id = labels[selected_label]
    try:
        invoice = get_invoice(invoice_id)
    except AgentAPIError as exc:
        st.error(f"Could not load selected invoice: {exc}")
        return

    with st.container(border=True):
        st.markdown(
            f'<div class="eyebrow">ACTIVE REVIEW</div><h2 style="color:#182a32;margin:.15rem 0">{invoice.get("file_name") or "Unknown file"}</h2>'
            f'<div style="color:#52656b">Invoice: {invoice.get("invoice_number") or "Pending extraction"} · '
            f'Vendor: {invoice.get("vendor_name") or "Unknown"} · PO: {invoice.get("po_number") or "Not extracted"}</div>',
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Current status", status_label(invoice.get("validation_status")))
        c2.metric("Invoice total", f"{invoice.get('currency') or ''} {invoice.get('total_amount') if invoice.get('total_amount') is not None else '—'}".strip())
        c3.metric("Discrepancies", len(invoice.get("discrepancies") or []))
    if invoice.get("source_available") is False:
        st.warning("The original source file is missing. Feedback can still be saved, but revalidation requires the source file to be restored.")
    render_hitl(invoice, invoice_id)


def render_hitl(invoice: dict[str, Any], invoice_id: str) -> None:
    file_name = invoice.get("file_name") or "Unknown file"
    status = str(invoice.get("validation_status") or "unknown").lower()
    feedback_history = invoice.get("feedback") or []
    line_items = invoice.get("line_items") or []
    st.markdown("### Human review workspace")
    st.markdown(f'<div class="soft-note"><b>Reviewing:</b> {file_name}<br><span class="small-muted">Invoice ID: {invoice_id} · Current status: {status_label(status)} · This form applies only to the selected invoice.</span></div>', unsafe_allow_html=True)
    if status in {"manual_review", "pending_review", "rejected"} or invoice.get("human_review_required"):
        st.warning("This invoice needs an auditor decision. Review each finding and confirm or correct the extracted values.")
    else:
        st.info("This invoice is not currently flagged for manual review. You can still record feedback or rerun validation.")

    with st.expander(f"Review history · {len(feedback_history)} previous entry/entries", expanded=bool(feedback_history)):
        if not feedback_history:
            st.caption("No human feedback has been saved for this invoice.")
        for entry in feedback_history:
            st.markdown(f"**{status_label(entry.get('decision'))}** · {entry.get('created_at') or 'Date unavailable'}")
            if entry.get("feedback"):
                st.write(entry["feedback"])
            if entry.get("corrections"):
                st.json(entry["corrections"])
            st.divider()

    # Show the source-of-truth PO from ERP beside the extracted invoice before editing.
    po_number = str(invoice.get("po_number") or "").strip()
    erp_po: dict[str, Any] | None = None
    st.markdown("### Compare invoice with ERP purchase order")
    if not po_number:
        st.warning("No purchase-order number was extracted, so ERP comparison is unavailable. Check the original invoice and correct the PO field through re-extraction or the source document.")
    else:
        try:
            erp_po = get_erp_purchase_order(po_number)
            st.caption(f"ERP reference · {erp_po.get('po_number')} · {erp_po.get('vendor_name') or 'Vendor not recorded'} · {erp_po.get('currency') or 'Currency not recorded'} · Status: {erp_po.get('status') or 'unknown'}")
            po_lines = erp_po.get("line_items") or []
            po_by_sku = {str(row.get("sku") or "").strip().casefold(): row for row in po_lines}
            comparison_rows = []
            for idx, item in enumerate(line_items):
                sku = str(item.get("sku") or item.get("item_code") or item.get("sku_code") or "").strip()
                po_line = po_by_sku.get(sku.casefold())
                comparison_rows.append({
                    "Line": item.get("line_number", idx + 1),
                    "Invoice SKU": sku or "—",
                    "Invoice description": item.get("description") or "—",
                    "Invoice qty": item.get("quantity") if item.get("quantity") is not None else "—",
                    "Invoice unit price": item.get("unit_price") if item.get("unit_price") is not None else "—",
                    "ERP SKU": (po_line or {}).get("sku", "No SKU match"),
                    "ERP description": (po_line or {}).get("description", "—"),
                    "ERP qty": (po_line or {}).get("quantity", "—"),
                    "ERP unit price": (po_line or {}).get("unit_price", "—"),
                    "ERP currency": (po_line or {}).get("currency") or erp_po.get("currency") or "—",
                })
            if comparison_rows:
                st.dataframe(pd.DataFrame(comparison_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No extracted invoice line items are available to compare.")
            with st.expander("Full ERP purchase order", expanded=False):
                st.write(f"**Vendor:** {erp_po.get('vendor_name') or '—'}")
                st.write(f"**PO status:** {erp_po.get('status') or '—'}")
                if po_lines:
                    st.dataframe(pd.DataFrame(po_lines), use_container_width=True, hide_index=True)
                else:
                    st.info("The ERP purchase order has no line items.")
        except AgentAPIError as exc:
            st.warning(f"Could not load ERP comparison: {exc}")
            st.caption("You can still review the extracted invoice values, but verify the purchase order in ERP before approving.")

    corrections: list[dict[str, Any]] = []
    if line_items:
        st.markdown("### Correct extracted invoice values")
        st.caption("Use the invoice-versus-ERP comparison above. Edit only values that are wrong on the invoice extraction; do not change the invoice just to force a match if the supplier really charged a different price.")
        st.caption("Each editor is labelled with its line number, SKU and description. Only values you change are sent as corrections.")
        for idx, item in enumerate(line_items):
            sku = str(item.get("sku") or item.get("item_code") or item.get("sku_code") or "")
            description = str(item.get("description") or "Description not extracted")
            line_no = item.get("line_number", idx + 1)
            qty_original = safe_float(item.get("quantity"))
            price_original = safe_float(item.get("unit_price"))
            line_total = item.get("line_total")
            with st.container(border=True):
                st.markdown(f"**Line {line_no} · {sku or 'SKU missing'}**")
                st.caption(description)
                meta1, meta2, meta3 = st.columns(3)
                meta1.write(f"Original quantity: **{qty_original:g}**")
                meta2.write(f"Original unit price: **{price_original:.2f}**")
                meta3.write(f"Original line total: **{line_total if line_total is not None else '—'}**")
                c1, c2, c3, c4 = st.columns([1.15, 0.9, 1.0, 1.1])
                with c1:
                    corrected_sku = st.text_input("Corrected SKU", value=sku, key=f"review_sku_{invoice_id}_{line_no}")
                with c2:
                    qty = st.number_input("Corrected quantity", min_value=0.0, value=qty_original, step=1.0, key=f"review_qty_{invoice_id}_{line_no}")
                with c3:
                    price = st.number_input("Corrected unit price", min_value=0.0, value=price_original, step=0.01, format="%.2f", key=f"review_price_{invoice_id}_{line_no}")
                with c4:
                    st.write("**Proposed line total**")
                    st.write(f"{qty * price:.2f}")
                corr: dict[str, Any] = {"line_number": line_no}
                changed = False
                if corrected_sku.strip() != sku:
                    corr["sku"] = corrected_sku.strip()
                    changed = True
                if qty != qty_original:
                    corr["quantity"] = qty
                    changed = True
                if price != price_original:
                    corr["unit_price"] = price
                    changed = True
                if changed:
                    corrections.append(corr)

    st.markdown("### Human feedback")
    feedback = st.text_area("Auditor notes", placeholder="Example: Compared line 2 against PO-1001; invoice shows $3.50 but ERP shows $3.00. Waiting for buyer approval.", key=f"review_feedback_{invoice_id}", height=110)
    feedback_col, action_col = st.columns([1, 2])
    with feedback_col:
        if st.button("Save feedback note only", key=f"save_feedback_only_{invoice_id}", use_container_width=True, disabled=not feedback.strip()):
            try:
                saved = save_human_feedback(invoice_id, feedback.strip())
                st.success(saved.get("message") or "Feedback saved. No revalidation was run.")
                st.rerun()
            except AgentAPIError as exc:
                st.error(f"Could not save feedback: {exc}")
    with action_col:
        st.caption("Saving a note alone records your observation without changing extracted values or running the audit again.")
    decision_options = ["Revalidate without changes", "Correct & revalidate", "Approve", "Reject"]
    decision = st.selectbox(
        "Revalidation / review action",
        decision_options,
        index=0,
        key=f"review_decision_{invoice_id}",
        help="Choose what to do with this selected invoice. Corrections are submitted only when you choose Correct & revalidate.",
    )
    action_help = {
        "Revalidate without changes": "Run extraction and audit validation again using the current source file.",
        "Correct & revalidate": "Save the edited line-item values, record your notes, then run validation again.",
        "Approve": "Record an auditor approval. Use only after checking the invoice and findings.",
        "Reject": "Record that this invoice should not be approved.",
    }
    st.caption(action_help[decision])
    if corrections and decision != "Correct & revalidate":
        st.warning(f"You changed {len(corrections)} line item(s). Choose ‘Correct & revalidate’ to submit those edits.")
    submit_disabled = invoice.get("source_available") is False and decision in {"Revalidate without changes", "Correct & revalidate"}
    action_button_label = {
        "Revalidate without changes": "Run revalidation",
        "Correct & revalidate": "Correct & revalidate",
        "Approve": "Save approval",
        "Reject": "Save rejection",
    }[decision]
    if st.button(action_button_label, type="primary", disabled=submit_disabled, key=f"submit_review_{invoice_id}", use_container_width=True):
        if decision == "Correct & revalidate" and not corrections and not feedback.strip():
            st.warning("Make a correction or add auditor notes before submitting this action.")
            return
        api_decision = {
            "Revalidate without changes": "revalidate", "Correct & revalidate": "corrected",
            "Approve": "approved", "Reject": "rejected",
        }[decision]
        payload = {"line_items": corrections} if corrections and decision == "Correct & revalidate" else {}
        try:
            with st.spinner(f"Saving review for {file_name} and updating the audit record…"):
                result = revalidate_invoice(invoice_id, corrections=payload, decision=api_decision, feedback=feedback.strip() or None)
            st.success(f"Review saved for {file_name}.")
            st.caption(f"Server response: {result.get('message') or 'Review request completed.'}")
            st.rerun()
        except AgentAPIError as exc:
            st.error(f"Review could not be saved for {file_name}: {exc}")


def render_upload_status(files: list[dict[str, Any]] | None = None, compact: bool = False) -> None:
    st.subheader("Incoming file queue" if not compact else "Source file status")
    if files is None:
        try:
            status_payload = get_upload_status()
            files = status_payload.get("files") or []
            incoming_path = status_payload.get("incoming_directory") or "/app/data/incoming"
        except AgentAPIError as exc:
            st.error(f"Could not fetch upload status: {exc}")
            return
    else:
        incoming_path = "/app/data/incoming"
    if not compact:
        st.caption(f"Incoming folder inside the Agent container: {incoming_path}")
        st.code("~/Desktop/ai_project/data/incoming", language="text")
        st.caption("Container mount: /app/data/incoming")
        st.caption("Files in this folder are picked up automatically. Clear pending files to remove only files that have not yet become saved invoices. Use the full reset only when you intentionally want to erase saved audit history and re-import the same files.")
    if not files:
        st.info("The queue is empty. Add files using the upload control above or copy them into the incoming folder.")
    else:
        rows = [{
            "Source file": item.get("file_name") or "Unknown file",
            "Invoice no.": item.get("invoice_number") or "Pending extraction",
            "Vendor": item.get("vendor_name") or "Pending extraction",
            "Status": status_label(item.get("status")),
            "Recommendation": status_label(item.get("recommendation")) if item.get("recommendation") else "—",
            "Invoice ID": str(item.get("invoice_id") or "Not assigned yet")[:12],
        } for item in files]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if not compact:
        action_col, reset_col = st.columns([1, 1.5])
        with action_col:
            if st.button("Clear pending queue", use_container_width=True, key="clear_pending_queue_btn"):
                try:
                    result = clear_pending_queue()
                    st.success(f"Removed {result.get('removed_count', 0)} pending file(s). Saved invoice sources were preserved.")
                    if result.get("skipped_count"):
                        st.info(f"Kept {result['skipped_count']} file(s) because they are already linked to saved invoices or currently processing.")
                    st.rerun()
                except AgentAPIError as exc:
                    st.error(f"Queue could not be cleared: {exc}")
        with reset_col:
            with st.expander("Start completely fresh (destructive)", expanded=False):
                st.warning("This deletes all saved invoice audit records, incoming source files, local reports and the invoice-vector collection. ERP seed data and the PostgreSQL volume are preserved. This cannot be undone.")
                with st.form("reset_invoice_workspace_form"):
                    confirmation = st.text_input("Type RESET-INVOICES to confirm")
                    submitted = st.form_submit_button("Reset invoice workspace", type="primary", use_container_width=True)
                if submitted:
                    if confirmation.strip() != "RESET-INVOICES":
                        st.error("Confirmation did not match. Nothing was reset.")
                    else:
                        try:
                            result = reset_invoice_workspace(confirmation.strip())
                            st.session_state.pop("last_upload_result", None)
                            st.session_state.pop("last_ask_result", None)
                            st.success(f"Workspace cleared. Removed {result.get('removed_source_files', 0)} source file(s) and {result.get('deleted_invoice_records', 0)} invoice record(s). You can now import a fresh set.")
                            st.rerun()
                        except AgentAPIError as exc:
                            st.error(f"Workspace reset failed: {exc}")
        if st.button("Refresh queue status", key="refresh_status_table"):
            st.rerun()

def upload_page() -> None:
    page_header("Upload center", "Add an invoice to the processing queue and track its status from upload through validation.", "INGESTION")
    left, right = st.columns([1.2, 1])
    with left, st.container(border=True):
        st.subheader("Upload a source document")
        st.caption("PDF, DOCX, PNG, JPG/JPEG or TIFF/TIF · maximum 25 MB")
        uploaded_file = st.file_uploader("Choose invoice file", type=["pdf", "docx", "png", "jpg", "jpeg", "tif", "tiff"], key="upload_file_picker")
        if uploaded_file:
            st.markdown(f"**Selected file:** `{uploaded_file.name}`")
            st.caption(f"Size: {uploaded_file.size / 1024:.1f} KB")
            if st.button("Upload invoice", type="primary", use_container_width=True, key="upload_invoice_submit"):
                try:
                    with st.spinner("Sending file to Agent API…"):
                        result = upload_invoice(uploaded_file.name, uploaded_file.getvalue())
                    st.session_state["last_upload_result"] = result
                    if result.get("status") == "duplicate":
                        st.warning("This exact file matches an existing audit record. No duplicate invoice record was created.")
                        st.write(f"Existing invoice: {result.get('invoice_number') or 'number pending'} · ID `{str(result.get('invoice_id') or '')[:12]}`")
                    else:
                        st.success("Upload received. Background processing will update the status table.")
                        st.write(f"Queue status: {status_label(result.get('status'))}")
                    st.rerun()
                except AgentAPIError as exc:
                    st.error(f"Upload failed: {exc}")
    with right, st.container(border=True):
        st.subheader("What happens next")
        for n, title, body in [
            ("01", "File received", "The API validates the file type and saves the source."),
            ("02", "Extraction & checks", "The watcher extracts fields and compares invoice values with ERP records."),
            ("03", "Audit result", "The record receives a validation status, recommendation and discrepancy list."),
            ("04", "Human review", "You can correct extracted line items, leave notes and revalidate."),
        ]:
            st.markdown(f"**{n} · {title}**")
            st.caption(body)
            st.divider()
    last = st.session_state.get("last_upload_result")
    if last:
        with st.container(border=True):
            st.subheader("Latest upload receipt")
            c1, c2, c3 = st.columns(3)
            c1.write("**Original filename**")
            c1.write(last.get("filename") or "—")
            c2.write("**Upload status**")
            c2.write(status_label(last.get("status")))
            c3.write("**Size received**")
            c3.write(f"{last.get('size_bytes', 0)} bytes")
    last = st.session_state.get("last_upload_result")
    if last:
        st.write("")
        with st.container(border=True):
            st.subheader("Processing stages")
            st.caption("A simple status view for the latest uploaded file. Refresh to see the watcher's latest state.")
            status_text = str(last.get("status") or "uploaded").lower()
            try:
                live_files = get_upload_status().get("files") or []
                uploaded_name = str(last.get("filename") or "")
                matched = next((f for f in live_files if str(f.get("file_name") or "") == uploaded_name), None)
                if matched:
                    status_text = str(matched.get("status") or status_text).lower()
            except AgentAPIError:
                pass
            stages = [
                ("1 · Received", True, "The API accepted the source file."),
                ("2 · Queued", status_text not in {"failed"}, "The file is saved in the incoming folder for the watcher."),
                ("3 · Extracted & checked", status_text in {"processed", "approved", "manual_review", "duplicate"} or "manual review" in status_text, "Invoice fields and ERP checks are available once processing finishes."),
                ("4 · Audit result", status_text in {"processed", "approved", "manual_review", "duplicate"} or "manual review" in status_text, "Open Invoices & Review to inspect line items and discrepancies."),
            ]
            cols = st.columns(4)
            for col, (label, done, description) in zip(cols, stages):
                with col:
                    st.markdown(f"<div class='{ 'stage-done' if done else 'stage-wait' }'>{'✓' if done else '○'} {label}</div>", unsafe_allow_html=True)
                    st.caption(description)
            if status_text in {"uploaded", "queued", "uploaded / queued"}:
                st.info("The watcher may still be processing this file. Use Refresh queue status below to update the stage view.")
    st.divider()
    render_upload_status()


def ask_ai_page() -> None:
    page_header("Ask AI", "Ask a question about one invoice or compare evidence across your saved audit records.", "INVOICE INTELLIGENCE")
    try:
        invoices = get_invoices()
        upload_files = get_upload_status().get("files") or []
    except AgentAPIError as exc:
        st.error(f"Could not load invoice choices: {exc}")
        if st.button("Retry loading invoices"):
            st.rerun()
        return

    invoice_by_id: dict[str, dict[str, Any]] = {}
    options = [{"label": "All processed invoices", "id": None, "pending": False}]
    seen_ids: set[str] = set()
    for invoice in invoices:
        iid = str(invoice.get("invoice_id") or "")
        if not iid:
            continue
        file_name = invoice.get("file_name") or "Unknown file"
        number = invoice.get("invoice_number") or "Number pending"
        vendor = invoice.get("vendor_name") or "Vendor unknown"
        status = status_label(invoice.get("validation_status"))
        options.append({"label": f"{file_name}  ·  {number}  ·  {vendor}  ·  {status}", "id": iid, "pending": False})
        invoice_by_id[iid] = invoice
        seen_ids.add(iid)
    for item in upload_files:
        iid = str(item.get("invoice_id") or "")
        if iid and iid in seen_ids:
            continue
        file_name = item.get("file_name") or "Unknown file"
        options.append({
            "label": f"{file_name}  ·  {item.get('invoice_number') or 'Number pending'}  ·  {item.get('vendor_name') or 'Vendor pending'}  ·  {status_label(item.get('status'))}",
            "id": iid or None, "pending": not bool(iid),
        })
        if iid:
            seen_ids.add(iid)

    with st.container(border=True):
        st.subheader("Choose your evidence scope")
        selected = st.selectbox("Invoice source", options, format_func=lambda x: x["label"], key="ask_ai_selected_file")
        if selected.get("pending"):
            st.info("This file exists in the incoming folder but has not been linked to a saved invoice record yet. Wait for processing, then refresh the choices.")
        elif selected.get("id"):
            chosen = invoice_by_id.get(selected["id"], {})
            st.markdown(f"**Selected source:** `{chosen.get('file_name') or selected['label']}`")
            st.caption(f"Invoice: {chosen.get('invoice_number') or 'pending'} · Vendor: {chosen.get('vendor_name') or 'pending'} · Current status: {status_label(chosen.get('validation_status'))} · ID: {selected['id']}")
        else:
            st.caption("Answers may combine facts from multiple saved invoices. Choose a specific invoice for precise discrepancy questions.")

        st.markdown("**Try a question**")
        suggestions = st.columns(3)
        suggested_questions = ["What discrepancies were found and why?", "Why does this invoice need manual review?", "Summarize the key invoice facts."]
        for col, sample in zip(suggestions, suggested_questions):
            if col.button(sample, key=f"suggest_{sample}", use_container_width=True):
                st.session_state["ask_ai_question"] = sample
        question = st.text_area("Your question", placeholder="Ask about totals, tax, purchase-order matching, SKU mismatches, validation status or recommended next steps…", height=115, key="ask_ai_question")
        submit = st.button("Generate answer", type="primary", use_container_width=True, key="ask_ai_submit")

    if submit:
        if not question.strip():
            st.warning("Enter a question first.")
            return
        if selected.get("pending"):
            st.warning("This file is still waiting for processing. Select it again after it receives an invoice ID.")
            return
        if selected["id"] is None and not invoices:
            st.warning("There are no saved invoices to search yet.")
            return
        try:
            with st.spinner("Retrieving invoice evidence and drafting an answer…"):
                result = ask_ai(question.strip(), invoice_id=selected["id"])
            st.session_state["last_ask_result"] = result
            st.session_state["last_ask_question"] = question.strip()
            st.rerun()
        except AgentAPIError as exc:
            st.error(f"Ask AI request failed: {exc}")

    result = st.session_state.get("last_ask_result")
    if result:
        st.write("")
        with st.container(border=True):
            st.markdown('<div class="eyebrow">ANSWER</div>', unsafe_allow_html=True)
            source = str(result.get("answer_source") or "rag").replace("_", " ").title()
            st.caption(f"For: {st.session_state.get('last_ask_question', '')}")
            st.markdown(f'<div class="answer-box">{_html_escape(str(result.get("answer") or "I could not produce an answer from the available evidence."))}</div>', unsafe_allow_html=True)
            if result.get("answer_needs_verification"):
                if result.get("answer_source") == "saved_audit_analysis":
                    st.info("This explanation uses the saved audit record because the language model was unavailable. Verify the flagged fields against the original invoice and purchase order before approving.")
                else:
                    st.info("Verify the flagged fields against the original invoice and purchase order before approving.")

        docs = result.get("documents") or []
        if docs:
            with st.expander(f"Evidence excerpts · {len(docs)} retrieved passage(s)", expanded=False):
                for idx, doc in enumerate(docs, 1):
                    title = f"{idx}. {doc.get('file_name') or 'Unknown file'} · {doc.get('invoice_number') or 'Invoice number pending'}"
                    with st.container(border=True):
                        st.markdown(f"**{title}**")
                        st.write(str(doc.get("text") or "No text excerpt was stored.")[:2200])
        if result.get("answer_source") in {"saved_audit_analysis", "hybrid_rag"}:
            with st.expander("What this answer is based on", expanded=False):
                st.write("Saved invoice fields, recorded discrepancies and stored line items are used as the source of truth for the current audit status.")
                st.write("Retrieved document passages are supporting evidence when available. Always compare proposed corrections with the original invoice and purchase order.")


def _html_escape(value: str) -> str:
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>").replace("\"", "&quot;"))


if __name__ == "__main__":
    main()
