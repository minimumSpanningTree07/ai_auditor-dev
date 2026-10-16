from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agent.nodes.business_validation import business_validate
from agent.nodes.data_validation import data_validate
from agent.nodes.extraction import extract_invoice
from agent.nodes.field_extraction import extract_fields
from agent.nodes.monitor import monitor_invoice
from agent.nodes.persistence import persist_invoice
from agent.nodes.reporting import generate_report
from agent.nodes.translation import translate_invoice
from agent.state import InvoiceState


def _should_continue_after_monitor(
    state: InvoiceState,
) -> str:
    if state.get("processing_status") in {
        "failed",
        "duplicate",
    }:
        return END

    return "extraction"


def _should_continue_after_extraction(
    state: InvoiceState,
) -> str:
    if state.get("processing_status") == "failed":
        return END

    return "translation"


def _should_continue_after_translation(
    state: InvoiceState,
) -> str:
    if state.get("processing_status") == "failed":
        return END

    return "field_extraction"


def _should_continue_after_persistence(
    state: InvoiceState,
) -> str:
    if state.get("persistence_status") == "failed":
        return END

    return "rag_indexing"


def _rag_indexing(
    state: InvoiceState,
) -> dict[str, Any]:
    """
    Index the completed invoice into the derived Qdrant index.

    RAG indexing failure must not invalidate invoice persistence.
    """

    try:
        from agent.rag.indexing import index_invoice

        result = index_invoice(state)

        return {
            **result,
            "processing_status": "complete",
        }

    except Exception as exc:
        return {
            "processing_status": "complete",
            "warnings": [
                *list(state.get("warnings") or []),
                f"RAG indexing failed: {exc}",
            ],
        }


def build_invoice_graph():
    """
    Build the complete invoice processing graph.

    Workflow:

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
          ↓
        RAG indexing
    """

    workflow = StateGraph(InvoiceState)

    workflow.add_node(
        "monitor",
        monitor_invoice,
    )

    workflow.add_node(
        "extraction",
        extract_invoice,
    )

    workflow.add_node(
        "translation",
        translate_invoice,
    )

    workflow.add_node(
        "field_extraction",
        extract_fields,
    )

    workflow.add_node(
        "business_validation",
        business_validate,
    )

    workflow.add_node(
        "data_validation",
        data_validate,
    )

    workflow.add_node(
        "reporting",
        generate_report,
    )

    workflow.add_node(
        "persistence",
        persist_invoice,
    )

    workflow.add_node(
        "rag_indexing",
        _rag_indexing,
    )

    workflow.add_edge(
        START,
        "monitor",
    )

    workflow.add_conditional_edges(
        "monitor",
        _should_continue_after_monitor,
        {
            "extraction": "extraction",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "extraction",
        _should_continue_after_extraction,
        {
            "translation": "translation",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "translation",
        _should_continue_after_translation,
        {
            "field_extraction": "field_extraction",
            END: END,
        },
    )

    workflow.add_edge(
        "field_extraction",
        "business_validation",
    )

    workflow.add_edge(
        "business_validation",
        "data_validation",
    )

    workflow.add_edge(
        "data_validation",
        "reporting",
    )

    workflow.add_edge(
        "reporting",
        "persistence",
    )

    workflow.add_conditional_edges(
        "persistence",
        _should_continue_after_persistence,
        {
            "rag_indexing": "rag_indexing",
            END: END,
        },
    )

    workflow.add_edge(
        "rag_indexing",
        END,
    )

    return workflow.compile()


invoice_graph = build_invoice_graph()


def process_invoice(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute invoice processing synchronously.
    """

    return invoice_graph.invoke(
        state
    )