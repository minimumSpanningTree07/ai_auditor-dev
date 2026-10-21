from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agent.rag.augmentation import augment_state
from agent.rag.generation import generate_for_state
from agent.rag.reflection import reflect_state
from agent.rag.retrieval import retrieve_for_state
from agent.rag.router import route_state
from agent.state import InvoiceState

from agent.nodes.monitor import monitor_invoice
from agent.nodes.extraction import extract_invoice
from agent.nodes.translation import translate_invoice
from agent.nodes.field_extraction import extract_fields
from agent.nodes.business_validation import business_validate as validate_business
from agent.nodes.data_validation import data_validate as validate_data
from agent.nodes.reporting import generate_report
from agent.nodes.persistence import persist_invoice


def _route_after_router(
    state: InvoiceState,
) -> str:
    route = state.get("rag_route")

    if route == "sql":
        return "sql"

    return "rag_retrieve"


def _route_after_reflection(
    state: InvoiceState,
) -> str:
    """
    Decide whether the RAG answer is good enough.

    Accepted:
        score >= 0.70

    Otherwise:
        retry retrieval/generation until the configured
        retry limit is reached.
    """

    if state.get("rag_answer_accepted"):
        return "rag_complete"

    retry_count = int(
        state.get("rag_retry_count") or 0
    )

    max_retries = int(
        state.get("rag_max_retries")
        or 3
    )

    if retry_count >= max_retries:
        return "rag_complete"

    return "rag_retry"


def _increment_retry(
    state: InvoiceState,
) -> dict[str, Any]:
    return {
        "rag_retry_count": int(
            state.get("rag_retry_count") or 0
        ) + 1
    }


def _complete_rag(
    state: InvoiceState,
) -> dict[str, Any]:
    return {
        "processing_status": "completed",
    }


def _structured_placeholder(
    state: InvoiceState,
) -> dict[str, Any]:
    """
    Structured questions are handled by the SQL answer layer.

    This node intentionally does not execute SQL.
    """

    return {
        "processing_status": "completed",
    }


def build_invoice_graph():
    """
    Build the invoice-auditing workflow.

    Normal invoice processing:

        monitor
          ↓
        extraction
          ↓
        translation
          ↓
        field extraction
          ↓
        business validation
          ↓
        data validation
          ↓
        reporting
          ↓
        persistence

    RAG questions are routed separately:

        router
          ↓
        retrieval
          ↓
        augmentation
          ↓
        generation
          ↓
        reflection
          ↓
        retry if score < threshold
    """

    graph = StateGraph(InvoiceState)

    # ---------------------------------------------------------
    # Invoice audit nodes
    # ---------------------------------------------------------

    graph.add_node(
        "monitor",
        monitor_invoice,
    )

    graph.add_node(
        "extraction",
        extract_invoice,
    )

    graph.add_node(
        "translation",
        translate_invoice,
    )

    graph.add_node(
        "field_extraction",
        extract_fields,
    )

    graph.add_node(
        "business_validation",
        validate_business,
    )

    graph.add_node(
        "data_validation",
        validate_data,
    )

    graph.add_node(
        "reporting",
        generate_report,
    )

    graph.add_node(
        "persistence",
        persist_invoice,
    )

    # ---------------------------------------------------------
    # RAG nodes
    # ---------------------------------------------------------

    graph.add_node(
        "rag_router",
        route_state,
    )

    graph.add_node(
        "rag_retrieval",
        retrieve_for_state,
    )

    graph.add_node(
        "rag_augmentation",
        augment_state,
    )

    graph.add_node(
        "rag_generation",
        generate_for_state,
    )

    graph.add_node(
        "rag_reflection",
        reflect_state,
    )

    graph.add_node(
        "rag_retry",
        _increment_retry,
    )

    graph.add_node(
        "rag_complete",
        _complete_rag,
    )

    graph.add_node(
        "sql_answer",
        _structured_placeholder,
    )

    # ---------------------------------------------------------
    # Invoice audit flow
    # ---------------------------------------------------------

    graph.add_edge(
        START,
        "monitor",
    )

    graph.add_edge(
        "monitor",
        "extraction",
    )

    graph.add_edge(
        "extraction",
        "translation",
    )

    graph.add_edge(
        "translation",
        "field_extraction",
    )

    graph.add_edge(
        "field_extraction",
        "business_validation",
    )

    graph.add_edge(
        "business_validation",
        "data_validation",
    )

    graph.add_edge(
        "data_validation",
        "reporting",
    )

    graph.add_edge(
        "reporting",
        "persistence",
    )

    graph.add_edge(
        "persistence",
        END,
    )

    # ---------------------------------------------------------
    # RAG question flow
    # ---------------------------------------------------------

    # The application can invoke rag_router directly
    # for question-answering requests.
    #
    # START → rag_router is intentionally NOT connected here,
    # because normal invoice processing must remain independent
    # from question answering.

    graph.add_conditional_edges(
        "rag_router",
        _route_after_router,
        {
            "sql": "sql_answer",
            "rag_retrieve": "rag_retrieval",
        },
    )

    graph.add_edge(
        "rag_retrieval",
        "rag_augmentation",
    )

    graph.add_edge(
        "rag_augmentation",
        "rag_generation",
    )

    graph.add_edge(
        "rag_generation",
        "rag_reflection",
    )

    graph.add_conditional_edges(
        "rag_reflection",
        _route_after_reflection,
        {
            "rag_retry": "rag_retry",
            "rag_complete": "rag_complete",
        },
    )

    graph.add_edge(
        "rag_retry",
        "rag_retrieval",
    )

    graph.add_edge(
        "rag_complete",
        END,
    )

    graph.add_edge(
        "sql_answer",
        END,
    )

    return graph.compile()


invoice_graph = build_invoice_graph()