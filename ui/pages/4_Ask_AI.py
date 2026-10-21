from __future__ import annotations
import streamlit as st
import pandas as pd
from shared import setup_page, header, status
from api_client import get_invoices, ask_ai, get_rag_evaluations, AgentAPIError

setup_page("Ask AI", "🤖")
header("Ask AI", "Structured questions go directly to PostgreSQL. Open-ended questions use current audit-table truth plus Qdrant retrieval and grounded generation.", "INVOICE INTELLIGENCE")
try: invoices=get_invoices()
except AgentAPIError as exc: st.error(str(exc)); st.stop()
opts=[("All invoices",None)]+[(f"{x.get('invoice_number') or x.get('file_name')} · {x.get('vendor_name') or 'Unknown'} · {status(x.get('validation_status'))}",x.get('invoice_id')) for x in invoices]
selected=st.selectbox("Evidence scope",range(len(opts)),format_func=lambda i:opts[i][0])
invoice_id=opts[selected][1]
with st.container(border=True):
    for q in ["What is the total amount?","What discrepancies are open?","Explain why this invoice needs human review.","Summarize the invoice and its audit history."]:
        if st.button(q,key=f"q_{q}"): st.session_state["question"]=q
    question=st.text_area("Question",value=st.session_state.get("question",""),height=110)
    go=st.button("Generate answer",type="primary",use_container_width=True)
if go and question.strip():
    try:
        with st.spinner("Routing, retrieving current evidence and evaluating the answer…"):
            st.session_state["ask_result"]=ask_ai(question.strip(),invoice_id=invoice_id)
            st.session_state["ask_question"]=question.strip()
    except AgentAPIError as exc: st.error(str(exc))

result=st.session_state.get("ask_result")
if result:
    st.subheader("Answer")
    st.markdown(f'<div class="answer">{result.get("answer") or "No answer generated."}</div>',unsafe_allow_html=True)
    st.caption(f"Route: {str(result.get('route') or result.get('answer_source') or 'rag').upper()} · accepted: {result.get('accepted')} · retries: {result.get('retry_count',0)}")
    if result.get("route")=="sql":
        st.success("Structured query answered with SQL only. No semantic generation was used.")
        if result.get("structured_data"): st.json(result["structured_data"])
    else:
        metrics=result.get("ragas") or {}
        st.subheader("RAG quality evaluation")
        cols=st.columns(5)
        vals=[("Faithfulness",metrics.get("faithfulness")),("Answer relevancy",metrics.get("answer_relevancy")),("Context relevance",metrics.get("context_relevance")),("Factual accuracy",metrics.get("factual_accuracy")),("Overall",metrics.get("overall"))]
        for col,(label,val) in zip(cols,vals): col.metric(label, "—" if val is None else f"{float(val):.2f}")
        st.caption(f"Evaluator source: {metrics.get('source','unknown')} · threshold: 0.70")
        reflection=result.get("reflection") or {}
        with st.expander("Reflection / RAG triad",expanded=False): st.json(reflection)
        docs=result.get("documents") or []
        if docs:
            with st.expander(f"Retrieved evidence ({len(docs)})",expanded=False):
                st.dataframe(pd.DataFrame([{k:d.get(k) for k in ["invoice_id","invoice_number","score","chunk_index","text"]} for d in docs]),use_container_width=True,hide_index=True)
        if invoice_id:
            try:
                history=get_rag_evaluations(invoice_id)
                with st.expander("Previous evaluations",expanded=False): st.dataframe(pd.DataFrame(history),use_container_width=True,hide_index=True)
            except AgentAPIError: pass
