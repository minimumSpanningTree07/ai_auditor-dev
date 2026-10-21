"""Per-answer RAGAS evaluation adapter."""
from __future__ import annotations
from typing import Any


def _clamp(value: Any) -> float:
    try: return round(max(0.0, min(1.0, float(value))), 4)
    except (TypeError, ValueError): return 0.0


def evaluate_answer(*, question: str, answer: str, contexts: list[str], reference: str | None = None) -> dict[str, Any]:
    contexts=[str(c).strip() for c in contexts if str(c).strip()]
    base={"available":False,"source":"unavailable","faithfulness":0.0,"answer_relevancy":0.0,"context_relevance":0.0,"factual_accuracy":0.0,"overall":0.0}
    try:
        from ragas import EvaluationDataset, evaluate
        from ragas.metrics import Faithfulness, ResponseRelevancy
        from langchain_core.embeddings import Embeddings
        from langchain_community.chat_models import ChatLiteLLM
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from litellm import embedding
        from agent.config import settings

        class _Embeddings(Embeddings):
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                r=embedding(model=settings.embedding_model,input=texts)
                return [x["embedding"] for x in r.data]
            def embed_query(self, text: str) -> list[float]:
                r=embedding(model=settings.embedding_model,input=[text])
                return r.data[0]["embedding"]

        llm=LangchainLLMWrapper(ChatLiteLLM(model=settings.rag_model, temperature=0))
        embeddings=LangchainEmbeddingsWrapper(_Embeddings())
        sample={"user_input":question,"response":answer,"retrieved_contexts":contexts}
        if reference: sample["reference"]=reference
        dataset=EvaluationDataset.from_list([sample])
        result=evaluate(dataset=dataset,metrics=[Faithfulness(),ResponseRelevancy()],llm=llm,embeddings=embeddings)
        values=result.to_pandas().iloc[0].to_dict()
        faithfulness=_clamp(values.get("faithfulness"))
        relevancy=_clamp(values.get("answer_relevancy",values.get("response_relevancy")))
        factual=round(min(faithfulness,relevancy),4)
        return {**base,"available":True,"source":"ragas","faithfulness":faithfulness,"answer_relevancy":relevancy,"context_relevance":relevancy,"factual_accuracy":factual,"overall":round((faithfulness+relevancy+factual)/3,4)}
    except Exception as exc:
        return {**base,"error":str(exc),"source":"reflection_fallback"}
