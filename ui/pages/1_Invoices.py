from __future__ import annotations
import streamlit as st
import pandas as pd
from shared import setup_page, header, status, fmt_money
from api_client import get_invoices, get_invoice, get_report, AgentAPIError

setup_page("Invoices")
header("Invoices", "Search the audit record, inspect validation results and open the generated report.", "AUDIT RECORDS")
try: invoices=get_invoices()
except AgentAPIError as exc: st.error(str(exc)); st.stop()
if not invoices:
    st.info("No invoices have been processed yet.")
    st.stop()

df=pd.DataFrame([{"Invoice":x.get("invoice_number") or "Pending", "Vendor":x.get("vendor_name") or "Unknown", "PO":x.get("po_number") or "—", "Total":fmt_money(x.get("total_amount"),x.get("currency")), "Status":status(x.get("validation_status")), "Recommendation":status(x.get("recommendation"))} for x in invoices])
st.dataframe(df,use_container_width=True,hide_index=True)
choice=st.selectbox("Open invoice", range(len(invoices)), format_func=lambda i:f"{invoices[i].get('invoice_number') or invoices[i].get('file_name')} · {invoices[i].get('vendor_name') or 'Unknown vendor'}")
inv=invoices[choice]
try: detail=get_invoice(str(inv["invoice_id"]))
except AgentAPIError as exc: st.error(str(exc)); st.stop()

c1,c2,c3,c4=st.columns(4)
c1.metric("Invoice",detail.get("invoice_number") or "Pending")
c2.metric("Vendor",detail.get("vendor_name") or "Unknown")
c3.metric("Total",fmt_money(detail.get("total_amount"),detail.get("currency")))
c4.metric("Open discrepancies",sum(1 for d in detail.get("discrepancies",[]) if str(d.get("status","")).lower()=="open"))

left,right=st.columns([1.2,.8])
with left, st.container(border=True):
    st.subheader("Current effective data")
    st.dataframe(pd.DataFrame([{k:detail.get(k) for k in ["invoice_number","vendor_name","po_number","invoice_date","currency","subtotal_amount","tax_amount","tax_rate","total_amount","validation_status","recommendation","human_review_required"]}]).T.rename(columns={0:"Value"}),use_container_width=True)
    st.subheader("Line items")
    st.dataframe(pd.DataFrame(detail.get("line_items") or []),use_container_width=True,hide_index=True)
with right, st.container(border=True):
    st.subheader("Discrepancies")
    disc=detail.get("discrepancies") or []
    if disc: st.dataframe(pd.DataFrame([{k:d.get(k) for k in ["discrepancy_type","severity","message","status"]} for d in disc]),use_container_width=True,hide_index=True)
    else: st.success("No recorded discrepancies.")
    st.subheader("Processing stage")
    st.write(detail.get("processing_stage") or "No live stage record")
    if st.button("Open Human Review",type="primary",use_container_width=True):
        st.switch_page("pages/2_Human_Review.py")
    if st.button("View JSON report",use_container_width=True):
        try: st.json(get_report(str(detail["invoice_id"])))
        except AgentAPIError as exc: st.error(str(exc))
