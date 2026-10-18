# UI and queue improvements

- Invoice review defaults to showing only invoices requiring human review. Toggle off to browse all saved invoices.
- Upload Center shows a compact stage tracker for the most recently uploaded file and displays the host and container incoming-directory paths.
- `DELETE /api/uploads/queue` removes only incoming files that do not match a saved invoice. Saved invoice source files and records are preserved.
- `POST /api/admin/reset-invoice-workspace` requires the exact confirmation string `RESET-INVOICES`. It deletes local incoming files, invoice-owned audit records (via FK cascade), report files and the configured Qdrant invoice collection. ERP seed data and the PostgreSQL volume remain intact.
- The full reset refuses to run while the watcher is processing a file.

The reset operation is destructive and should only be used when intentionally starting a fresh invoice import. It is not a substitute for a database backup.
