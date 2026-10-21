from __future__ import annotations

from typing import Any
import html
import streamlit as st
import pandas as pd

from api_client import AgentAPIError, get_dashboard_summary, get_invoices, get_upload_status, health

STATUS_META = {
    "approved": ("Approved", "success"),
    "complete": ("Complete", "success"),
    "manual_review": ("Human review", "warning"),
    "failed": ("Failed", "error"),
    "invalid_erp": ("Invalid ERP", "error"),
    "processing": ("Processing", "info"),
    "queued": ("Queued", "info"),
    "waiting": ("Waiting", "warning"),
}

def setup_page(title: str, icon: str = "🧾") -> None:
    st.set_page_config(page_title=f"{title} · AI Invoice Auditor", page_icon=icon, layout="wide")
    st.markdown("""
    <style>
    :root { --ink:#17212b; --muted:#66727d; --line:#e3e8ed; --bg:#f6f8fa; --card:#ffffff; --brand:#0f766e; --brand2:#115e59; }
    .stApp { background:var(--bg); }
    .block-container { max-width:1480px; padding-top:1.7rem; padding-bottom:3rem; }
    [data-testid="stSidebar"] { background:#102a2b; }
    [data-testid="stSidebar"] * { color:#e8f2f1 !important; }
    [data-testid="stMetric"] { background:white; border:1px solid var(--line); border-radius:16px; padding:1rem 1.1rem; box-shadow:0 4px 14px rgba(15,23,42,.04); }
    [data-testid="stMetricValue"] { color:#102a43; font-weight:800; }
    [data-testid="stMetricLabel"] { color:#66727d; font-weight:650; }
    div[data-testid="stVerticalBlockBorderWrapper"] { background:white; border:1px solid var(--line); border-radius:16px; }
    .title { font-size:2.05rem; font-weight:850; letter-spacing:-.04em; color:#102a43; margin:0; }
    .subtitle { color:#66727d; font-size:1rem; margin:.4rem 0 1.4rem; }
    .eyebrow { text-transform:uppercase; letter-spacing:.12em; font-size:.72rem; color:var(--brand); font-weight:800; }
    .hero { background:linear-gradient(135deg,#103f3b,#0f766e); color:white; border-radius:20px; padding:1.5rem 1.7rem; margin-bottom:1.2rem; }
    .hero h2 { color:white !important; margin:0; }
    .hero p { color:#d6efec !important; margin:.45rem 0 0; }
    .stage-card { background:white; border:1px solid var(--line); border-radius:14px; padding:1rem; min-height:118px; }
    .stage-name { font-weight:800; color:#102a43; }
    .stage-value { font-size:1.7rem; font-weight:850; margin-top:.3rem; }
    .stage-note { color:#66727d; font-size:.82rem; }
    .answer { background:#fff; border:1px solid #dfe7ee; border-left:4px solid var(--brand); border-radius:14px; padding:1.2rem 1.3rem; line-height:1.65; }
    .metric-card { background:#fff; border:1px solid var(--line); border-radius:14px; padding:1rem; }
    .small { color:#66727d; font-size:.85rem; }
    .pill { display:inline-block; padding:.25rem .55rem; border-radius:999px; background:#eef5f4; color:#0f5f59; font-size:.78rem; font-weight:750; }
    </style>
    """, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("## 🧾 AI Invoice Auditor")
        st.caption("Audit control room")
        st.divider()
        st.page_link("app.py", label="Dashboard", icon="📊")
        st.page_link("pages/1_Invoices.py", label="Invoices", icon="🗂️")
        st.page_link("pages/2_Human_Review.py", label="Human Review", icon="👤")
        st.page_link("pages/3_Upload_Center.py", label="Upload Center", icon="⬆️")
        st.page_link("pages/4_Ask_AI.py", label="Ask AI", icon="🤖")
        st.divider()
        try:
            health_result = health()
            st.success("All core services online" if health_result.get("status") == "healthy" else "Service attention needed")
        except Exception:
            st.error("Agent API unavailable")

def header(title: str, subtitle: str, eyebrow: str) -> None:
    st.markdown(f'<div class="eyebrow">{html.escape(eyebrow)}</div><h1 class="title">{html.escape(title)}</h1><div class="subtitle">{html.escape(subtitle)}</div>', unsafe_allow_html=True)

def status(value: Any) -> str:
    key = str(value or "unknown").lower().replace(" ", "_")
    return STATUS_META.get(key, (str(value or "Unknown").replace("_", " ").title(), "info"))[0]

def load_overview():
    return get_dashboard_summary(), get_invoices(), get_upload_status().get("files", [])

def fmt_money(value: Any, currency: Any = "") -> str:
    if value is None or value == "": return "—"
    try: return f"{currency or ''} {float(value):,.2f}".strip()
    except Exception: return f"{currency or ''} {value}".strip()
