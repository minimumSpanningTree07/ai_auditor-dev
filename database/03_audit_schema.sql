CREATE SCHEMA IF NOT EXISTS audit;


CREATE TABLE IF NOT EXISTS audit.invoices (
    id BIGSERIAL PRIMARY KEY,

    invoice_id VARCHAR(128) NOT NULL UNIQUE,

    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_checksum VARCHAR(128),
    file_size BIGINT,

    invoice_number VARCHAR(128),
    vendor_name TEXT,
    po_number VARCHAR(128),
    invoice_date DATE,
    currency VARCHAR(16),

    subtotal_amount NUMERIC(18, 4),
    tax_amount NUMERIC(18, 4),
    tax_rate NUMERIC(10, 6),
    total_amount NUMERIC(18, 4),

    raw_extracted_text TEXT,
    translated_text TEXT,
    source_language VARCHAR(32),

    extraction_method VARCHAR(64),
    extraction_confidence NUMERIC(6, 4),

    translation_used BOOLEAN NOT NULL DEFAULT FALSE,
    translation_confidence NUMERIC(6, 4),

    validation_status VARCHAR(32),
    recommendation VARCHAR(64),
    human_review_required BOOLEAN NOT NULL DEFAULT FALSE,

    report_path TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS audit.invoice_extractions (
    id BIGSERIAL PRIMARY KEY,

    invoice_id VARCHAR(128) NOT NULL UNIQUE
        REFERENCES audit.invoices(invoice_id)
        ON DELETE CASCADE,

    extracted_invoice_number VARCHAR(128),
    extracted_vendor_name TEXT,
    extracted_po_number VARCHAR(128),
    extracted_invoice_date DATE,
    extracted_currency VARCHAR(16),

    extracted_subtotal_amount NUMERIC(18, 4),
    extracted_tax_amount NUMERIC(18, 4),
    extracted_tax_rate NUMERIC(10, 6),
    extracted_total_amount NUMERIC(18, 4),

    extracted_line_items JSONB NOT NULL DEFAULT '[]'::JSONB,

    raw_text TEXT,

    extraction_method VARCHAR(64),
    extraction_confidence NUMERIC(6, 4),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS audit.invoice_line_items (
    id BIGSERIAL PRIMARY KEY,

    invoice_id VARCHAR(128) NOT NULL
        REFERENCES audit.invoices(invoice_id)
        ON DELETE CASCADE,

    line_number INTEGER NOT NULL,

    sku VARCHAR(128),
    description TEXT,

    quantity NUMERIC(18, 4),
    unit_price NUMERIC(18, 4),
    line_total NUMERIC(18, 4),

    source VARCHAR(32) NOT NULL DEFAULT 'extraction',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (invoice_id, line_number)
);


CREATE TABLE IF NOT EXISTS audit.discrepancies (
    id BIGSERIAL PRIMARY KEY,

    invoice_id VARCHAR(128) NOT NULL
        REFERENCES audit.invoices(invoice_id)
        ON DELETE CASCADE,

    discrepancy_type VARCHAR(128) NOT NULL,
    severity VARCHAR(32) NOT NULL,

    message TEXT NOT NULL,

    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS audit.human_feedback (
    id BIGSERIAL PRIMARY KEY,

    invoice_id VARCHAR(128) NOT NULL
        REFERENCES audit.invoices(invoice_id)
        ON DELETE CASCADE,

    decision VARCHAR(64),

    feedback TEXT,

    corrections JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS audit.audit_events (
    id BIGSERIAL PRIMARY KEY,

    invoice_id VARCHAR(128)
        REFERENCES audit.invoices(invoice_id)
        ON DELETE CASCADE,

    event_type VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,

    payload JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS idx_audit_invoices_invoice_number
    ON audit.invoices (invoice_number);

CREATE INDEX IF NOT EXISTS idx_audit_invoices_vendor
    ON audit.invoices (vendor_name);

CREATE INDEX IF NOT EXISTS idx_audit_invoices_status
    ON audit.invoices (validation_status);

CREATE INDEX IF NOT EXISTS idx_audit_invoices_checksum
    ON audit.invoices (file_checksum);

CREATE INDEX IF NOT EXISTS idx_audit_line_items_invoice
    ON audit.invoice_line_items (invoice_id);

CREATE INDEX IF NOT EXISTS idx_audit_discrepancies_invoice
    ON audit.discrepancies (invoice_id);

CREATE INDEX IF NOT EXISTS idx_audit_feedback_invoice
    ON audit.human_feedback (invoice_id);

CREATE INDEX IF NOT EXISTS idx_audit_events_invoice
    ON audit.audit_events (invoice_id);


CREATE OR REPLACE FUNCTION audit.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


DROP TRIGGER IF EXISTS trg_audit_invoices_updated_at
ON audit.invoices;

CREATE TRIGGER trg_audit_invoices_updated_at
BEFORE UPDATE ON audit.invoices
FOR EACH ROW
EXECUTE FUNCTION audit.update_updated_at();


DROP TRIGGER IF EXISTS trg_audit_discrepancies_updated_at
ON audit.discrepancies;

CREATE TRIGGER trg_audit_discrepancies_updated_at
BEFORE UPDATE ON audit.discrepancies
FOR EACH ROW
EXECUTE FUNCTION audit.update_updated_at();
CREATE TABLE IF NOT EXISTS audit.processing_jobs (
    id BIGSERIAL PRIMARY KEY,
    invoice_id VARCHAR(128),
    file_name TEXT NOT NULL,
    file_checksum VARCHAR(128),
    stage VARCHAR(64) NOT NULL DEFAULT 'uploaded',
    stage_label TEXT NOT NULL DEFAULT 'Uploaded',
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    message TEXT,
    progress_percent INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processing_jobs_checksum ON audit.processing_jobs(file_checksum);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_invoice ON audit.processing_jobs(invoice_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_updated ON audit.processing_jobs(updated_at DESC);

CREATE TABLE IF NOT EXISTS audit.rag_evaluations (
    id BIGSERIAL PRIMARY KEY,
    invoice_id VARCHAR(128),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    route VARCHAR(32) NOT NULL DEFAULT 'rag',
    metrics JSONB NOT NULL DEFAULT '{}'::JSONB,
    overall_score NUMERIC(8,4),
    accepted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_evaluations_invoice ON audit.rag_evaluations(invoice_id);
CREATE INDEX IF NOT EXISTS idx_rag_evaluations_created ON audit.rag_evaluations(created_at DESC);
