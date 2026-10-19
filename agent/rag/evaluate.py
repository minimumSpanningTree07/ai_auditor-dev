"""Run an offline-style RAG quality evaluation against a JSONL gold set.

Each input JSONL row must contain: question, reference; optional invoice_id.
Requires configured LiteLLM/Bedrock credentials and a reachable Qdrant collection.
Run from the project root inside the agent container:
  python -m agent.rag.evaluate --dataset agent/rag/evaluation_dataset.jsonl --output outputs/rag_eval_results.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_community.chat_models import ChatLiteLLM
from litellm import embedding
from ragas import EvaluationDataset, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    ResponseRelevancy,
)

from agent.config import settings
from agent.rag.generation import generate
from agent.rag.retrieval import retrieve


class LiteLLMEmbeddings(Embeddings):
    """LangChain embedding adapter using the project's configured LiteLLM model."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = embedding(model=settings.embedding_model, input=texts)
        return [item["embedding"] for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        response = embedding(model=settings.embedding_model, input=[text])
        return response.data[0]["embedding"]


def _load_dataset(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
            if not str(row.get("question", "")).strip() or not str(row.get("reference", "")).strip():
                raise ValueError(f"Line {line_number} must contain non-empty question and reference fields")
            rows.append(row)
    if not rows:
        raise ValueError(f"No evaluation cases found in {path}")
    return rows


def run_evaluation(dataset_path: Path, output_path: Path) -> dict[str, Any]:
    cases = _load_dataset(dataset_path)
    records: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        question = str(case["question"]).strip()
        invoice_id = str(case.get("invoice_id") or "").strip() or None
        docs = retrieve(question=question, invoice_id=invoice_id)
        contexts = [str(doc.get("text") or "").strip() for doc in docs]
        contexts = [context for context in contexts if context]
        context = "\n\n".join(contexts)
        answer = generate(question=question, context=context)
        records.append({
            "user_input": question,
            "retrieved_contexts": contexts,
            "response": answer,
            "reference": str(case["reference"]).strip(),
        })
        print(f"[{index}/{len(cases)}] evaluated retrieval/generation for: {question[:90]}")

    judge_model = ChatLiteLLM(model=settings.rag_model, temperature=0)
    judge_llm = LangchainLLMWrapper(judge_model)
    judge_embeddings = LangchainEmbeddingsWrapper(LiteLLMEmbeddings())
    metrics = [
        Faithfulness(llm=judge_llm),
        ResponseRelevancy(llm=judge_llm, embeddings=judge_embeddings),
        LLMContextPrecisionWithReference(llm=judge_llm),
        LLMContextRecall(llm=judge_llm),
    ]
    result = evaluate(
        dataset=EvaluationDataset.from_list(records),
        metrics=metrics,
        llm=judge_llm,
        embeddings=judge_embeddings,
        raise_exceptions=True,
    )
    frame = result.to_pandas()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    scores: dict[str, Any] = {}
    for column in frame.columns:
        if column not in {"user_input", "retrieved_contexts", "response", "reference"}:
            numeric = frame[column].dropna()
            if len(numeric):
                scores[column] = round(float(numeric.mean()), 4)
    summary_path = output_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps({
        "dataset": str(dataset_path),
        "cases": len(records),
        "mean_scores": scores,
        "results_csv": str(output_path),
    }, indent=2), encoding="utf-8")
    print(json.dumps({"cases": len(records), "mean_scores": scores, "csv": str(output_path), "summary": str(summary_path)}, indent=2))
    return {"cases": len(records), "mean_scores": scores}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate invoice-auditor RAG with Ragas")
    parser.add_argument("--dataset", type=Path, default=Path("agent/rag/evaluation_dataset.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("outputs/rag_eval_results.csv"))
    args = parser.parse_args()
    if not args.dataset.exists():
        raise SystemExit(f"Evaluation dataset not found: {args.dataset}")
    run_evaluation(args.dataset, args.output)


if __name__ == "__main__":
    main()
