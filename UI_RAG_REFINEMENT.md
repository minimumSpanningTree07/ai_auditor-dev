# UI and RAG refinement notes

## UI changes
- Reworked navigation and page hierarchy into Dashboard, Invoices & Human Review, Upload Center, and Ask AI.
- Dashboard highlights invoice totals, audit outcomes, recent activity, queue status, and review attention.
- Invoice register includes search and a detailed selected-invoice header so the filename and invoice ID remain visible while reviewing.
- Invoice details are grouped into Overview, Line Items, Discrepancies, and Human Review tabs.
- Human review shows original quantity, unit price, line total, proposed line total, invoice filename, invoice ID, current status, feedback history, and explicit action descriptions.
- Upload center explains the watcher lifecycle and displays source file processing status.
- Ask AI keeps evidence excerpts and quality diagnostics collapsed by default; it labels the evidence source and warns when the evaluator could not confirm answer quality.

## RAG changes
- Fixed the retrieval cutoff so the semantic retrieval score threshold is not incorrectly reused as the LLM answer-quality threshold. Similarity values around 0.1–0.3 can still be useful and should reach the grounded generation step.
- The selected invoice's authoritative saved audit facts (fields, line items, discrepancy messages, validation status and recommendation) are combined with retrieved text before answer generation.
- A saved audit record remains available as evidence if Qdrant has no matching passage or returns weak scores.
- Answer generation is handled as a string, matching the current `generate()` function contract.
- Reflection/evaluator failure no longer discards an otherwise generated answer; the response is explicitly marked as requiring verification.
- The generation prompt now asks for direct, focused answers, plain-language explanation of discrepancies, and no generic summary unless requested.

## Preservation notes
- The Compose AWS shared-configuration mount remains `/home/labuser/.aws:/root/.aws:ro`.
- The archive intentionally excludes `.env`, `.git`, `data/incoming`, and `outputs/reports`; extracting it does not overwrite the local environment or local invoice/report files.
- No database or Qdrant volumes are removed by these changes.

## Validation
- Python compilation passed.
- Project test suite: 4 passed in the available local environment.
- Live Docker, PostgreSQL, Qdrant and AWS Bedrock integration must still be checked on the Ubuntu host.
