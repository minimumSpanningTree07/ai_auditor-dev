from __future__ import annotations
import streamlit as st
from shared import setup_page, header, load_overview, status, fmt_money

setup_page("Dashboard")
header("Audit control room", "A clean operational view of invoice intake, validation, human review and RAG readiness.", "OVERVIEW")
try:
    summary, invoices, uploads = load_overview()
except Exception as exc:
    st.error(f"Could not load dashboard: {exc}")
    st.stop()

st.markdown('<div class="hero"><h2>Invoice audit, from intake to decision</h2><p>Every file moves through extraction → translation → validation → ERP business validation → report → human review when needed → RAG.</p></div>', unsafe_allow_html=True)
cols=st.columns(5)
for col,(label,val) in zip(cols,[
    ("Total invoices",summary.get("total_invoices",len(invoices))),
    ("Approved",summary.get("approved_invoices",summary.get("approved",0))),
    ("Human review",summary.get("review_invoices",summary.get("manual_review",0))),
    ("Open discrepancies",summary.get("open_discrepancies",summary.get("total_discrepancies",0))),
    ("Files in pipeline",len(uploads)),
]): col.metric(label,val or 0)

if st.button("↻ Refresh dashboard",use_container_width=False): st.rerun()
st.subheader("Live processing pipeline")
active=[x for x in uploads if str(x.get("status") or "").lower() in {"queued","processing","waiting"}]
st.caption("The stage below is read from the agent's operational status table. Refresh the page to poll the latest state.")
st.dataframe([
    {"File":x.get("file_name"),"Stage":x.get("stage_label") or status(x.get("stage")),"Progress":f"{x.get('progress_percent',0)}%","Status":status(x.get("status")),"Message":x.get("message") or "","Updated":x.get("updated_at") or "—"}
    for x in uploads
], use_container_width=True, hide_index=True)

st.subheader("Recent audit decisions")
rows=[]
for x in invoices[:12]:
    rows.append({"Invoice":x.get("invoice_number") or "Pending", "Vendor":x.get("vendor_name") or "Unknown", "PO":x.get("po_number") or "—", "Total":fmt_money(x.get("total_amount"),x.get("currency")), "Status":status(x.get("validation_status")), "Recommendation":status(x.get("recommendation")), "Updated":x.get("updated_at") or "—"})
st.dataframe(rows,use_container_width=True,hide_index=True)

if active:
    st.info(f"{len(active)} file(s) are still moving through the pipeline. Open **Upload Center** for live stage details.")
