# Correction notes

## Corrected defects

- Fixed the duplicate-detection bug in `agent/nodes/monitor.py`: the watcher supplies the current file's checksum in the initial state, so comparing that value with the checksum computed by the monitor classified every fresh upload as a duplicate. Duplicate detection now checks the persisted audit table instead.
- Added `.docx` support to the monitor and extraction node; paragraphs and table rows are extracted as text.
- Updated the watcher to process unchanged files once, retry failures after a cooldown, run synchronous graph work in a worker thread, and log workflow failures.
- Configured application logging so watcher progress is visible in container logs.
- Replaced the obsolete second graph in `agent/main.py` with a compatibility import of the canonical FastAPI app. The watcher and API now use `agent.graph` as the single workflow implementation.
- Added PyMuPDF and language detection dependencies; installed English, Spanish and German Tesseract language packs in the agent image.
- Separated agent, Mock ERP and UI dependency installs; added a root Docker build ignore file and Dockerfile-specific ignore files.
- Pinned the Qdrant image, removed Redis's unnecessary persistent volume, and removed the machine-specific `/home/labuser/.aws` mount.
- Removed the local `.env` and Git history from this delivery. A safe `.env.example` is included instead.

## Verification performed here

- Python syntax compilation passed for `agent`, `mock_erp`, `ui`, and `tests`.
- The included unit tests passed (2 passed).
- `compose.yml` parsed as valid YAML and defines all six services.
- Docker is not installed in the correction environment, so image builds and a real end-to-end run against PostgreSQL, Redis, Qdrant, AWS Bedrock and Mock ERP could not be executed here.

## Before running

1. Copy `.env.example` to `.env`.
2. Set `POSTGRES_PASSWORD` to a strong random alphanumeric value (for example, generate one with `openssl rand -hex 32`).
3. Configure AWS Bedrock credentials through your local environment or `.env` if using static keys. Do not commit `.env`.
4. Start with `docker compose -f compose.yml up --build -d`.
5. Check `docker compose -f compose.yml ps` and `docker compose -f compose.yml logs --tail=150 agent`.

The uploaded archive included a local `.env` file. It is deliberately excluded from this corrected package. Rotate any real password or cloud credential that was stored in that file.
