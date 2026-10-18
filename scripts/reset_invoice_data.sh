#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

cat <<'NOTICE'
This reset removes existing AUDIT invoice records, invoice files in data/incoming,
JSON audit reports in outputs/reports, and the configured Qdrant invoice collection.
It does NOT remove ERP seed tables/data, the PostgreSQL volume, AWS config/credentials,
or Docker volumes. Make a backup first if these invoice records may be needed.
NOTICE
read -r -p 'Type RESET-INVOICES to continue: ' confirmation
if [[ "$confirmation" != "RESET-INVOICES" ]]; then
  echo "Cancelled; no data was changed."
  exit 0
fi

# Pause the watcher to prevent it from re-processing files while the reset runs.
docker compose stop agent
restart_agent() { docker compose start agent >/dev/null 2>&1 || true; }
trap restart_agent EXIT

# Use the known owner for the existing database first, then fall back to the
# Compose-configured user for fresh installations.
if ! docker compose exec -T postgres sh -lc 'psql -U invoice_auditor_app -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "TRUNCATE TABLE audit.invoices RESTART IDENTITY CASCADE;"' 2>/dev/null; then
  docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "TRUNCATE TABLE audit.invoices RESTART IDENTITY CASCADE;"'
fi

mkdir -p data/incoming outputs/reports
sudo find data/incoming -maxdepth 1 -type f \( -iname '*.pdf' -o -iname '*.docx' -o -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.tif' -o -iname '*.tiff' -o -name '*.meta.json' \) -delete
sudo find outputs/reports -maxdepth 1 -type f -name '*.json' -delete
sudo chown -R 10001:10001 data/incoming outputs/reports
sudo chmod -R u+rwX,g+rwX data/incoming outputs/reports

collection="$(sed -n 's/^QDRANT_COLLECTION=//p' .env 2>/dev/null | head -n1)"
collection="${collection:-invoice_documents}"
python3 - "$collection" <<'PY'
import sys
import urllib.error
import urllib.request
collection = sys.argv[1]
url = f"http://localhost:6339/collections/{collection}"
request = urllib.request.Request(url, method="DELETE")
try:
    with urllib.request.urlopen(request, timeout=10) as response:
        print(f"Cleared Qdrant invoice collection {collection!r}: HTTP {response.status}")
except urllib.error.HTTPError as exc:
    if exc.code == 404:
        print(f"Qdrant collection {collection!r} did not exist; nothing to clear.")
    else:
        raise
PY

restart_agent
trap - EXIT
echo "Invoice audit data cleared. ERP data and AWS configuration were preserved."
