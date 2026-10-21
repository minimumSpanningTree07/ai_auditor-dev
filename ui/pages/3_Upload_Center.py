from __future__ import annotations
import streamlit as st
import pandas as pd
from shared import setup_page, header, status
from api_client import upload_invoice, get_upload_status, clear_pending_queue, AgentAPIError

setup_page("Upload Center")
header("Upload center", "Drop invoices into the monitored queue and watch every processing stage in real time.", "INGESTION")

file=st.file_uploader("Upload PDF, DOCX or scanned image",type=["pdf","docx","png","jpg","jpeg","tif","tiff"])
if file and st.button("Start processing",type="primary"):
    try:
        result=upload_invoice(file.name,file.getvalue())
        st.session_state["last_upload"] = result
        st.success(result.get("message") or "File accepted")
    except AgentAPIError as exc: st.error(str(exc))

st.subheader("Live queue")
st.caption("Refresh to poll the agent. A file remains visible at its exact stage until the workflow advances or fails.")
if st.button("↻ Refresh queue",use_container_width=True): st.rerun()
try: files=get_upload_status().get("files") or []
except AgentAPIError as exc: st.error(str(exc)); st.stop()

for f in files:
    with st.container(border=True):
        top=st.columns([2.2,1,1,1])
        top[0].markdown(f"**{f.get('file_name') or 'Unknown file'}**")
        top[1].write(status(f.get("status")))
        top[2].write(f"{f.get('progress_percent',0)}%")
        top[3].write(f.get("invoice_number") or "Pending")
        st.progress(min(100,max(0,int(f.get("progress_percent") or 0))))
        st.caption(f"**{f.get('stage_label') or f.get('stage') or 'Queued'}** · {f.get('message') or ''}")
        if f.get("error"): st.error(f["error"])
        if f.get("invoice_id"): st.caption(f"Invoice ID: {f['invoice_id']}")

st.divider()
if st.button("Clear pending uploads",use_container_width=True):
    try: st.success(clear_pending_queue().get("message")); st.rerun()
    except AgentAPIError as exc: st.error(str(exc))
