from __future__ import annotations


from typing import Any






def indexing_agent(state: dict[str, Any]) -> dict[str, Any]:
    text = state.get("raw_extracted_text") or state.get("translated_text") or ""
    return {
        "documents": [{"text": text, "invoice_id": state.get("invoice_id"), "source_type": "invoice"}],
        "current_stage": "rag_indexing_completed",
    }




def retrieval_agent(state: dict[str, Any]) -> dict[str, Any]:
    question = state.get("question") or ""
    context = state.get("report_summary") or state.get("raw_extracted_text") or ""
    return {
        "context": context,
        "question": question,
        "retries": int(state.get("retries", 0)) + 1,
        "current_stage": "rag_retrieval_completed",
    }




def augmentation_agent(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "context": state.get("context") or state.get("report_summary") or "",
        "current_stage": "rag_augmentation_completed",
    }




def generation_agent(state: dict[str, Any]) -> dict[str, Any]:
    question = state.get("question") or ""
    context = state.get("context") or ""
    answer = f"Answer based on invoice context. Question: {question}. Context: {context}" if context else "No context available."
    return {
        "answer": answer,
        "current_stage": "rag_generation_completed",
    }




def reflection_agent(state: dict[str, Any]) -> dict[str, Any]:
    score = 0.8 if state.get("answer") else 0.0
    return {
        "score": score,
        "relevance": score,
        "groundedness": score,
        "context_relevance": score,
        "current_stage": "rag_reflection_completed",
    }


