# AI Invoice Auditor

Containerized invoice auditing system: extraction/OCR, multilingual translation, validation against the Mock ERP HTTP API, audit persistence, reports, Qdrant RAG, and a Streamlit review UI.

## Start locally

1. Install Docker Engine and Docker Compose v2.
2. Create a local environment file: `cp .env.example .env`. Edit `.env` and replace `POSTGRES_PASSWORD` with a strong random password. Configure AWS credentials using your normal credential chain or local environment variables. Never commit `.env`.
3. Start the stack: `docker compose -f compose.yml up --build -d`.
4. Check health: `docker compose -f compose.yml ps`; open the UI at `http://localhost:8503`, agent API at `http://localhost:8010/health`, and Mock ERP at `http://localhost:8009/health`. PostgreSQL is exposed on host port `5434` and Qdrant on `6339`; services still use their internal container ports.
5. Upload a PDF/DOCX/image using the UI or `POST /api/invoices/upload`. The watcher scans `/app/data/incoming`, processes unchanged files once, and retries failures after a cooldown.

To stop while preserving PostgreSQL and Qdrant data: `docker compose -f compose.yml down`. Do not use `-v` unless you intentionally want to delete persistent data.

## Services

- `agent`: FastAPI and the canonical LangGraph workflow (`agent.graph`), exposed on host port 8010 / container port 8000.
- `mock-erp`: ERP lookups over HTTP on host port 8009 / container port 8000. The agent must not query ERP tables directly.
- `ui`: Streamlit on container port 8501, exposed on host port 8503.
- `postgres`: durable audit data and LangGraph checkpoints.
- `qdrant`: durable vector index, rebuildable from persisted invoice text.
- `redis`: disposable cache.

## Notes

- The `agent/main.py` module is a compatibility import of the canonical FastAPI app; the old second graph implementation was removed to avoid divergent imports.
- PDF/image OCR requires the Tesseract language packs listed in the agent Dockerfile. Configure `OCR_LANGUAGES` to match installed packs.
- Never place credentials in source files, Dockerfiles, images, or version control. The archive used for this correction contained a local `.env`; it has intentionally been excluded from the corrected package. Rotate any real credentials/passwords that were present in that file.

## Existing PostgreSQL volumes

The init scripts run only for a brand-new PostgreSQL data directory. If your current database volume already exists, changing `POSTGRES_USER` in `.env` will not create that role or change its password. Keep the volume; verify roles with `docker compose exec postgres psql -U invoice_auditor_app -d invoice_auditor -c \\du` and align the application role/password deliberately before restarting dependent services. Do not use `docker compose down -v` to fix credentials.


## Clear old invoice test data safely

To remove prior invoice audit records/files and the invoice RAG collection while preserving ERP seed data and AWS configuration, run `bash scripts/reset_invoice_data.sh` and type `RESET-INVOICES` when prompted. This is destructive for invoice audit history; back up first if needed. It does not remove PostgreSQL or Docker volumes.

The Upload Invoice page shows queued, processing, and processed status. The Invoices page provides revalidation and human-feedback history for all invoices, not only those currently marked for manual review.

## RAG quality evaluation (Ragas)

The project includes an optional Ragas evaluation runner. It evaluates the existing Qdrant retrieval and LiteLLM answer-generation path; it does not replace either component. The evaluator uses the configured `RAG_MODEL` as its judge and the configured `EMBEDDING_MODEL` for answer-relevancy embeddings, so the same provider credentials/permissions are required.

1. Edit `agent/rag/evaluation_dataset.jsonl` and replace each starter `reference` with a **specific, verified expected answer** from your invoice/policy corpus. Add `invoice_id` to a row when the question should be scoped to one invoice. The shipped references are starter templates, not a gold-standard benchmark.
2. Rebuild the agent image so the optional evaluation dependencies are installed:

   ```bash
   docker compose build agent
   docker compose up -d agent
   ```

3. Run evaluation from the project root inside the agent container:

   ```bash
   docker compose exec agent python -m agent.rag.evaluate \
     --dataset agent/rag/evaluation_dataset.jsonl \
     --output outputs/rag_eval_results.csv
   ```

The command writes per-question scores to `outputs/rag_eval_results.csv` and aggregate mean scores to `outputs/rag_eval_results.summary.json`. Metrics are Faithfulness, Response Relevancy, Context Precision, and Context Recall. Evaluation makes model/API calls and may incur provider charges; it requires a populated Qdrant collection and valid model credentials. It is an explicit command and does not run on every invoice audit.
