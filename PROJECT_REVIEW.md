# Project review and fixes

## Fixed in this package

- Aligned the ERP seed SQL and Python seed script with the canonical `database/01_erp_schema.sql` tables (`erp.vendors`, `erp.skus`, `erp.purchase_orders`, `erp.purchase_order_lines`). The previous seed script created/inserted into incompatible `sku_master`/`po_line_items` columns and could stop fresh database initialization.
- Rewrote Mock ERP queries to use the canonical schema and removed the duplicate `/vendor/search` route.
- Corrected structured discrepancy queries to match `audit.discrepancies` columns.
- Added the missing `InvalidOperation` import used during invoice-line correction.
- Fixed dashboard metric key mismatches and discrepancy detail display.
- Improved Ask AI with a dropdown whose options show the actual invoice filename, invoice number, vendor and status; added a refresh action, clearer fetch errors, longer timeout only for AI queries, and visible retrieved source chunks.
- Expanded upload format choices to match the API-supported formats.
- Repaired `.env.example` formatting and removed all credentials from that template.
- Fixed `database/seed_erp.py` default data path so it works from the checked-out project rather than assuming `/app`.
- Updated README service URLs to match the selected host ports.
- Set host ports to 5434 (Postgres), 6339 (Qdrant), 8009 (Mock ERP), 8010 (Agent); internal container ports and service URLs remain unchanged.

## AWS configuration preserved

The AWS-related Compose environment variables, `AWS_SHARED_CREDENTIALS_FILE`, `AWS_CONFIG_FILE`, and the read-only `/home/labuser/.aws:/root/.aws:ro` mount were deliberately left unchanged. No AWS shared config or credentials file is included in this package or modified by these edits.

## Important existing-database note

PostgreSQL init scripts only run when the data directory is first initialized. Updating these seed files does not repair a database volume that already exists. Do not run `docker compose down -v`. For an existing database, first inspect schemas and roles, then apply a deliberate migration/seed; the package does not automatically alter or drop live tables.

## Verification limits

Python source syntax compilation passed for all `.py` files; the included tests passed (2 passed); the Compose file retains all three protected AWS config/mount lines. Docker services, PostgreSQL credentials, Bedrock access, Qdrant connectivity, and full invoice processing still need to be tested on the Ubuntu host because those services/credentials are not available in this review environment.


## Follow-up UI/status changes
- Added `/api/uploads/status` for incoming and processed file status.
- Preserves the original upload filename in a safe UUID-prefixed stored filename and displays the original filename in the UI/database.
- Human review can now be opened for approved invoices too; supports revalidate without changes, corrections, approve/reject, and previous feedback history.
- Added a confirmation-protected reset script that clears only invoice audit records, incoming invoice files, generated JSON reports, and the configured Qdrant invoice collection. It does not alter AWS configuration or ERP seed data.


## Additional fixes (2026-10-18)
- Watcher now scans all existing incoming files on each poll and retries failed files after cooldown, rather than only processing files discovered once at startup.
- Original upload names are preserved in invoice records.
- Duplicate uploads are explicitly linked to the existing invoice record and update its source path, allowing later revalidation.
- Revalidation searches the incoming folder by checksum when the stored file path is stale; if missing, it returns HTTP 409 with a re-upload instruction.
- Ask AI now falls back to persisted invoice, discrepancy, and line-item data when semantic retrieval/evaluation cannot support an answer.
- Ask AI lists pending uploaded files as pending instead of silently omitting them.
- Reset script uses sudo for file cleanup and restores UID 10001 ownership.
- UI host port is 8503 to avoid the user's existing listeners on 8501 and 8502.

- PostgreSQL checkpointer now connects with explicit connection parameters rather than a raw interpolated DATABASE_URL, so passwords with URL-reserved characters are supported.
- Manual-review invoices are indexed before the workflow exits; Ask AI can query them before a reviewer approves them.
- Invoice detail view reports whether its source file is available for revalidation.
