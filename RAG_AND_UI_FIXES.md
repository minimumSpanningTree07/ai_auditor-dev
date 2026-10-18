# RAG and UI reliability fixes

## What changed

- Ask AI now falls back to a deterministic explanation assembled from saved invoice, discrepancy, and line-item rows when Bedrock answer generation fails. It does not pretend that a failed model call is a successful LLM answer.
- Bedrock generation tries the configured RAG model and then the configured primary model once. Provider exceptions are logged by type rather than repeatedly retried with the same prompt.
- The RAG pipeline stops retrying immediately after provider/generation or evaluator failures; the API can then use the saved-audit answer path.
- Duplicate detection returns the canonical saved invoice ID when a file checksum is already known, preventing a new watcher UUID from being shown as a second invoice.
- Qdrant client is pinned to the 1.13/1.14-compatible range for the Qdrant server 1.13.2 used by Compose.
- The sidebar no longer renders a Streamlit `DeltaGenerator` object from a conditional expression. User-facing Ask AI no longer shows raw evaluator exceptions, zero-score diagnostics, or semantic similarity numbers.
- UI palette is consistent deep teal / slate / warm neutral rather than mixing blue themes.

## Important deployment note

The existing local `.env` is intentionally not included or overwritten. In that file, set the answer model to the Nova model already configured for this project:

```dotenv
RAG_MODEL=bedrock/amazon.nova-lite-v1:0
LLM_MODEL=bedrock/amazon.nova-lite-v1:0
```

Confirm that the AWS account and selected region have access to this Bedrock model. If the model is not enabled for your account/region, select another chat model available there and set both values consistently. Keep `EMBEDDING_MODEL=bedrock/amazon.titan-embed-text-v1`; changing embedding models requires rebuilding the Qdrant vectors, so do not change it casually.

## Deploy

```bash
cd ~/Desktop/ai_project
# Edit the existing .env as noted above; do not share it or paste its secrets into logs.
docker compose config --quiet
docker compose up -d --build agent ui
docker compose ps
```

No database volume reset is required. Existing duplicate rows from earlier runs are not automatically deleted by this patch; new duplicate detections will reuse the existing invoice ID.

## Validation limits

Python compilation, Compose YAML parsing, and the focused RAG/business-validation tests pass in the build workspace. A full API test run requires all application dependencies and a live PostgreSQL/Qdrant/Bedrock setup; the updated services have not been integration-tested against your machine's cloud account.
