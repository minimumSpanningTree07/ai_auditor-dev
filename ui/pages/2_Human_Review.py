from __future__ import annotations
import streamlit as st
import pandas as pd
from shared import setup_page, header, status, fmt_money
from api_client import get_invoices, get_invoice, get_comparison, revalidate_invoice, AgentAPIError

setup_page("Human Review")
header("Human review", "Compare the immutable PDF extraction with the current effective values and ERP reference before revalidation.", "HUMAN-IN-THE-LOOP")
try: invoices=get_invoices()
except AgentAPIError as exc: st.error(str(exc)); st.stop()
review=[x for x in invoices if bool(x.get("human_review_required")) or str(x.get("validation_status","")).lower() in {"manual_review","failed","invalid_erp"}]
source=review or invoices
if not source:
    st.success("No invoices require human review.")
    st.stop()
choice=st.selectbox("Invoice requiring attention", range(len(source)), format_func=lambda i:f"{source[i].get('invoice_number') or source[i].get('file_name')} · {source[i].get('vendor_name') or 'Unknown'} · {status(source[i].get('validation_status'))}")
invoice_id=str(source[choice]["invoice_id"])
try: comparison=get_comparison(invoice_id); detail=comparison["invoice"]
except AgentAPIError as exc: st.error(str(exc)); st.stop()

if detail.get("validation_status")=="invalid_erp": st.error("ERP record not found / ERP validation failed. This invoice is invalid and the workflow will not continue to RAG until ERP data exists.")

st.markdown(f"### {detail.get('invoice_number') or 'Invoice'} · {detail.get('vendor_name') or 'Unknown vendor'}")
st.caption(f"Current status: {status(detail.get('validation_status'))} · recommendation: {status(detail.get('recommendation'))}")

orig=comparison.get("original_extraction") or {}
pdf_lines=orig.get("extracted_line_items") or []
current_lines=comparison.get("current_line_items") or []
erp=comparison.get("erp") or {}
po=erp.get("purchase_order") or {}
erp_lines=po.get("line_items") or []

st.subheader("Field comparison")
fields=[("Invoice number","extracted_invoice_number","invoice_number"),("Vendor","extracted_vendor_name","vendor_name"),("PO number","extracted_po_number","po_number"),("Invoice date","extracted_invoice_date","invoice_date"),("Currency","extracted_currency","currency"),("Subtotal","extracted_subtotal_amount","subtotal_amount"),("Tax","extracted_tax_amount","tax_amount"),("Tax rate","extracted_tax_rate","tax_rate"),("Total","extracted_total_amount","total_amount")]
rows=[]
for label,a,b in fields:
    rows.append({"Field":label,"PDF extracted":orig.get(a),"Current effective":detail.get(b),"ERP/reference":po.get({"PO number":"po_number","Currency":"currency","Vendor":"vendor_name"}.get(label,"")) if label in {"PO number","Currency","Vendor"} else "—","Different?":str(orig.get(a))!=str(detail.get(b))})
st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

st.subheader("Line-item comparison")
maxn=max(len(current_lines),len(erp_lines),1)
line_rows=[]
for i in range(maxn):
    cur=current_lines[i] if i<len(current_lines) else {}
    er=erp_lines[i] if i<len(erp_lines) else {}
    pdf=pdf_lines[i] if i<len(pdf_lines) else {}
line_rows.append({"Line":i+1,"SKU (PDF)":pdf.get("sku"),"SKU (current)":cur.get("sku"),"SKU (ERP)":er.get("sku") or er.get("sku_code"),"Qty (PDF)":pdf.get("quantity"),"Qty (current)":cur.get("quantity"),"Qty (ERP)":er.get("quantity"),"Price (PDF)":pdf.get("unit_price"),"Price (current)":cur.get("unit_price"),"Price (ERP)":er.get("unit_price") or er.get("price"),"Diff PDF→ERP": any(str(pdf.get(k))!=str(er.get(k2)) for k,k2 in [("sku","sku"),("quantity","quantity"),("unit_price","unit_price")]),"Diff current→ERP": any(str(cur.get(k))!=str(er.get(k2)) for k,k2 in [("sku","sku"),("quantity","quantity"),("unit_price","unit_price")])})
st.dataframe(pd.DataFrame(line_rows),use_container_width=True,hide_index=True)

st.divider()
st.subheader("Correct effective values")
st.caption("Corrections are appended to human feedback and revalidated. The original PDF extraction is never overwritten.")
with st.form("review_form"):
    scalar={}
    c1,c2,c3=st.columns(3)
    scalar["invoice_number"]=c1.text_input("Invoice number",value=str(detail.get("invoice_number") or ""))
    scalar["vendor_name"]=c2.text_input("Vendor",value=str(detail.get("vendor_name") or ""))
    scalar["po_number"]=c3.text_input("PO number",value=str(detail.get("po_number") or ""))
    c4,c5,c6=st.columns(3)
    scalar["invoice_date"]=c4.text_input("Invoice date",value=str(detail.get("invoice_date") or ""))
    scalar["currency"]=c5.text_input("Currency",value=str(detail.get("currency") or ""))
    scalar["total_amount"]=c6.number_input("Total",value=float(detail.get("total_amount") or 0),format="%.2f")
    st.markdown("**Line items**")
    corrected=[]
    for i,item in enumerate(current_lines):
        c=st.columns(5)
        corrected.append({"line_number":i+1,"sku":c[0].text_input(f"SKU {i+1}",value=str(item.get("sku") or ""),key=f"sku_{i}"),"description":c[1].text_input(f"Description {i+1}",value=str(item.get("description") or ""),key=f"desc_{i}"),"quantity":c[2].number_input(f"Qty {i+1}",value=float(item.get("quantity") or 0),key=f"qty_{i}"),"unit_price":c[3].number_input(f"Unit price {i+1}",value=float(item.get("unit_price") or 0),key=f"price_{i}"),"line_total":c[4].number_input(f"Line total {i+1}",value=float(item.get("line_total") or 0),key=f"line_{i}")})
    feedback=st.text_area("Auditor note",placeholder="Explain why the correction was made…")
    decision=st.selectbox("Decision",["revalidate","approve","reject"])
    submit=st.form_submit_button("Apply correction & revalidate",type="primary",use_container_width=True)
if submit:
    corrections={k:v for k,v in scalar.items() if v not in {"",None}}
    corrections["line_items"]=corrected
    try:
        result=revalidate_invoice(invoice_id,corrections=corrections,decision=decision,feedback=feedback or None)
        st.success(f"Revalidation complete: {status(result.get('validation_status'))} · {status(result.get('recommendation'))}")
        if result.get("discrepancies"): st.dataframe(pd.DataFrame(result["discrepancies"]),use_container_width=True,hide_index=True)
        else: st.success("All active discrepancies are resolved. The current audit table is clean.")
        st.rerun()
    except AgentAPIError as exc: st.error(str(exc))
