Mock ERP Setup
Overview
This module provides a mock ERP system for the AI Invoice Auditor project. It uses PostgreSQL to store vendor, SKU, and purchase-order data, while a FastAPI application exposes the data through REST APIs.
Docker Compose automates database initialization, dummy data seeding, and API startup.

Tech Stack
Python 3.12 — application and seed scripts
FastAPI — Mock ERP REST API
PostgreSQL 16 — database
Psycopg — PostgreSQL connectivity
Docker & Docker Compose — containerization and orchestration

Project Structure

project-root/
├── compose.yaml
├── .env
├── .env.example
├── database/
│   ├── schemas.sql
│   ├── erp_schema.sql
│   ├── audit_schema.sql
│   ├── seed_erp.py
│   └── dockerfile.seed
├── data/
│   └── ERP_mockdata/
│       ├── vendors.json
│       ├── sku_master.json
│       └── purchase_orders.json
└── mock_erp/
    ├── Dockerfile
    ├── main.py
    ├── database.py
    └── requirements.txt

Run the Application

1. Start the services

Run this command from the project root:

docker compose up --build -d

This builds the images and starts PostgreSQL, the ERP seed service, and Mock ERP in dependency order.

2. Check container status

docker compose ps -a

Expected behavior:

postgres — running and healthy

erp-seed — exits with code 0 after successfully inserting data

mock-erp — remains running

3. Inspect logs

docker compose logs postgres
docker compose logs erp-seed
docker compose logs mock-erp

4. Test the API

Open the interactive API documentation:

http://localhost:8001/docs

Test the health endpoint:

curl http://localhost:8001/health

Test vendor retrieval:

curl http://localhost:8001/vendor/VEND-001

Test purchase-order retrieval:

curl http://localhost:8001/po/PO-1001

These endpoints assume they are implemented in mock_erp/main.py.

Access PostgreSQL

Connect to the database through the Docker container:

docker compose exec postgres psql -U auditor -d invoice_auditor

List schemas:

\dn

List ERP tables:

\dt erp.*

Query vendors:

SELECT * FROM erp.vendors;

Query purchase orders:

SELECT * FROM erp.purchase_orders;

Query purchase-order line items:

SELECT * FROM erp.po_line_items;

Exit the PostgreSQL terminal:

\q

Stop the Application

Stop and remove the containers:

docker compose down

The named PostgreSQL volume remains, so database data is preserved.

Restart later with:

docker compose up -d

Warning: The following command deletes Compose-managed volumes, including the persistent database volume:

docker compose down -v

Use it only when you intentionally want to reset the stored database data.

Troubleshooting

PostgreSQL fails to start

docker compose logs postgres

Check the PostgreSQL password configuration and SQL initialization files.

Mock ERP exits unexpectedly

docker compose logs --tail=100 mock-erp

Check Python imports, installed dependencies, database connectivity, and the application traceback.

Seed service fails

docker compose logs erp-seed

Verify that the JSON files exist at the configured ERP_MOCKDATA_DIR and that their contents are valid JSON.