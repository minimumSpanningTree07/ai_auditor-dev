
from langgraph.graph import StateGraph, START, END

from agents.state import InvoiceState

from agents.nodes.monitor import monitor_node
from agents.nodes.extractor import (
    extract_invoice_info,
    extract_pdf,
    extract_docx,
    extract_image,
)
from agents.nodes.translation import translate_invoice_info

from agents.rag.rag import (
    indexing_agent,
    retrieval_agent,
    augmentation_agent,
    generation_agent,
    reflection_agent,
)

# Replace these imports with your actual module/function names.
from agents.nodes.field_extractor import extract_invoice_fields
from agents.nodes.business_validation import business_validation
from agents.nodes.data_validation import validate_invoice
from agents.nodes.reporting import reporting_node


# --------------------------------------------------
# ROUTING FUNCTIONS
# --------------------------------------------------

def route_start(state: InvoiceState) -> str:
    """Choose invoice processing or RAG question answering."""
    if state.get("question"):
        return "rag_retrieval"

    return "monitor"


def route_after_monitor(state: InvoiceState) -> str:
    """Stop for duplicates or idle state; otherwise extract."""
    if state.get("is_duplicate"):
        return "end"

    if state.get("processing_status") == "idle":
        return "end"

    return "extract_router"


def route_extractor(state: InvoiceState) -> str:
    file_type = state.get("file_type", "").lower()

    if file_type == ".pdf":
        return "extract_pdf"

    if file_type == ".docx":
        return "extract_docx"

    if file_type in {".png", ".jpg", ".jpeg"}:
        return "extract_image"

    raise ValueError(f"Unsupported file type: {file_type}")


def route_after_reflection(state: InvoiceState) -> str:
    score = state.get("score", 0.0)
    retries = state.get("retries", 0)

    if score >= 0.7 or retries >= 3:
        return "end"

    return "rag_retrieval"


# --------------------------------------------------
# BUILD GRAPH
# --------------------------------------------------

builder = StateGraph(InvoiceState)

# Monitoring and extraction
builder.add_node("monitor", monitor_node)
builder.add_node("extract_router", extract_invoice_info)
builder.add_node("extract_pdf", extract_pdf)
builder.add_node("extract_docx", extract_docx)
builder.add_node("extract_image", extract_image)

# Invoice processing
builder.add_node("translate", translate_invoice_info)
builder.add_node("field_extraction", extract_invoice_fields)
builder.add_node("business_validation", business_validation)
builder.add_node("validation", validate_invoice)
builder.add_node("reporting", reporting_node)

# RAG
builder.add_node("rag_indexing", indexing_agent)
builder.add_node("rag_retrieval", retrieval_agent)
builder.add_node("rag_augmentation", augmentation_agent)
builder.add_node("rag_generation", generation_agent)
builder.add_node("rag_reflection", reflection_agent)


# --------------------------------------------------
# ENTRY ROUTING
# --------------------------------------------------

builder.add_conditional_edges(
    START,
    route_start,
    {
        "monitor": "monitor",
        "rag_retrieval": "rag_retrieval",
    },
)


# --------------------------------------------------
# MONITOR -> EXTRACTION
# --------------------------------------------------

builder.add_conditional_edges(
    "monitor",
    route_after_monitor,
    {
        "end": END,
        "extract_router": "extract_router",
    },
)

builder.add_conditional_edges(
    "extract_router",
    route_extractor,
    {
        "extract_pdf": "extract_pdf",
        "extract_docx": "extract_docx",
        "extract_image": "extract_image",
    },
)


# --------------------------------------------------
# INVOICE PROCESSING PIPELINE
# --------------------------------------------------

builder.add_edge("extract_pdf", "translate")
builder.add_edge("extract_docx", "translate")
builder.add_edge("extract_image", "translate")

builder.add_edge("translate", "field_extraction")
builder.add_edge("field_extraction", "business_validation")
builder.add_edge("business_validation", "validation")
builder.add_edge("validation", "reporting")
builder.add_edge("reporting", "rag_indexing")

# Finish invoice processing after indexing.
builder.add_edge("rag_indexing", END)


# --------------------------------------------------
# RAG QUESTION-ANSWERING PIPELINE
# --------------------------------------------------

builder.add_edge("rag_retrieval", "rag_augmentation")
builder.add_edge("rag_augmentation", "rag_generation")
builder.add_edge("rag_generation", "rag_reflection")

builder.add_conditional_edges(
    "rag_reflection",
    route_after_reflection,
    {
        "end": END,
        "rag_retrieval": "rag_retrieval",
    },
)


# Compile the complete application graph.
app = builder.compile()

