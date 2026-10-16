# AI Invoice Auditor

Containerized AI-powered invoice auditing system for invoice extraction, translation, ERP validation, discrepancy detection, reporting, human feedback, and RAG-based invoice Q&A.

## Architecture

Services:

- Agent API: `8000`
- Mock ERP API: `8001`
- Streamlit UI: `8501`
- PostgreSQL: `5432`
- Qdrant: `6333`
- Redis: `6379`

The Agent communicates with ERP data only through the Mock ERP HTTP API.

## Workflow

```text
Invoice
   ↓
Monitor
   ↓
Extraction / OCR
   ↓
Translation
   ↓
Field Extraction
   ↓
Business Validation
   ↓
Data Validation
   ↓
Reporting
   ↓
Persistence
   ↓
Qdrant Indexing