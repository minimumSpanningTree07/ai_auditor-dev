# Runtime diagnostic fixes — 18 October 2026

## Confirmed from the supplied logs and source

1. **Upload HTTP 500 / permission denied:** the Agent runs as UID 10001, while bind-mounted incoming/report directories were not writable. The reset script now deletes those files with `sudo` and restores UID 10001 ownership afterward.
2. **Duplicate upload was confusing:** checksum duplicate detection stopped the workflow before creating another invoice, but did not relink the existing row to the newly uploaded file. Duplicate uploads now report the existing invoice ID and repair the stored source path.
3. **Revalidation returned “Original invoice file no longer exists”:** database file paths can become stale after folder changes or cleanup. Revalidation now searches the incoming folder by stored SHA-256 checksum, updates the path when found, and returns HTTP 409 with a clear re-upload instruction if not found.
4. **Ask AI showed “No answer generated” and zero scores:** RAG returned insufficient evidence and did not have a database fallback. The API now answers from persisted invoice/discrepancy/line-item records when semantic retrieval is insufficient or unavailable, and the UI labels that response as a database fallback instead of showing misleading zero-score metrics.
5. **Manual-review invoices could be absent from Qdrant:** the graph paused at the human-review interrupt before RAG indexing. The workflow now indexes each successfully persisted invoice before exiting; the review UI remains responsible for feedback and revalidation.
6. **Watcher did not retry existing failed files:** it only processed paths that were new since the last scan, so a failed file could be forgotten. It now scans all files each poll, while completed file signatures and retry cooldowns prevent needless reprocessing.
7. **File picker omitted unprocessed uploads:** Ask AI now lists uploaded-but-not-processed files as pending and tells the user to refresh rather than silently omitting them.
8. **Original file names were replaced by storage-prefixed names:** the monitor now preserves the original filename supplied by the watcher.
9. **PostgreSQL checkpointer connection used a raw URL:** special characters in a password could break the URL. The graph now connects with explicit psycopg parameters; the Compose `DATABASE_URL` interpolation was removed for the Agent.
10. **Port collisions:** host port 8501 and 8502 were occupied by other containers, so this Compose file maps the UI to host port 8503 while leaving the container port 8501 intact.

## AWS configuration

The Compose values `AWS_SHARED_CREDENTIALS_FILE`, `AWS_CONFIG_FILE`, and the read-only `/home/labuser/.aws:/root/.aws:ro` mount were preserved. No `.env`, AWS credentials, Git metadata, or local invoice/report data is included in this ZIP.

## Verification performed here

- Python compilation for `agent`, `ui`, and `mock_erp`: passed.
- Included pytest suite (`PYTHONPATH=. pytest -q`): 2 passed.
- Reset shell script syntax (`bash -n`): passed.
- Compose YAML parse: passed.
- A live Docker Compose validation/build and live database/Qdrant/AWS integration test could not be run in this environment because Docker is unavailable here; run the deployment commands on the Ubuntu host.
