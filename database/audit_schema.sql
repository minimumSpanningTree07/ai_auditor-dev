
CREATE SCHEMA IF NOT EXISTS audit;

-- 1. Main invoice audit table
CREATE TABLE IF NOT EXISTS audit.invoice_audit (
    invoice_id UUID PRIMARY KEY,
    vendor_id VARCHAR(50),
    file_path VARCHAR(512),
    file_checksum VARCHAR(64) UNIQUE,
    extraction_method VARCHAR(32),
    raw_extracted_text TEXT,
    translated_text TEXT,
    source_language VARCHAR(8),
    translation_confidence NUMERIC(4,3),
    invoice_number VARCHAR(64),
    vendor_name VARCHAR(255),
    po_number VARCHAR(64),
    invoice_date DATE,
    currency CHAR(3),
    total_amount NUMERIC(14,2),
    validation_status VARCHAR(32),
    recommendation VARCHAR(32),
    extracted_raw JSONB,
    report_summary TEXT,
    report_json JSONB,
    missing_fields JSONB DEFAULT '[]'::jsonb,
    thread_id VARCHAR(128),
    processed_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Invoice line items
CREATE TABLE IF NOT EXISTS audit.invoice_line_items (
    id BIGSERIAL PRIMARY KEY,
    invoice_id UUID NOT NULL
        REFERENCES audit.invoice_audit(invoice_id) ON DELETE CASCADE,
    line_number INTEGER,
    item_code VARCHAR(64),
    description TEXT,
    quantity NUMERIC(12,3),
    unit_price NUMERIC(14,4),
    line_total NUMERIC(14,2)
);

-- 3. Detected discrepancies
CREATE TABLE IF NOT EXISTS audit.discrepancies (
    id BIGSERIAL PRIMARY KEY,
    invoice_id UUID NOT NULL
        REFERENCES audit.invoice_audit(invoice_id) ON DELETE CASCADE,
    field_name VARCHAR(64),
    invoice_value TEXT,
    erp_value TEXT,
    deviation_pct NUMERIC(8,4),
    severity VARCHAR(16),
    detected_at TIMESTAMPTZ DEFAULT now()
);

-- 4. Human feedback and corrections
CREATE TABLE IF NOT EXISTS audit.human_feedback (
    id BIGSERIAL PRIMARY KEY,
    invoice_id UUID NOT NULL
        REFERENCES audit.invoice_audit(invoice_id) ON DELETE CASCADE,
    field_name VARCHAR(64),
    original_value TEXT,
    corrected_value TEXT,
    corrected_by VARCHAR(128),
    comments TEXT,
    corrected_at TIMESTAMPTZ DEFAULT now(),
    revalidated BOOLEAN DEFAULT FALSE
);

-- 5. Incoming file monitoring
CREATE TABLE IF NOT EXISTS audit.file_monitor (
    id BIGSERIAL PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_checksum VARCHAR(64),
    file_type VARCHAR(16),
    processing_status VARCHAR(20) NOT NULL DEFAULT 'detected',
    error_message TEXT,
    detected_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (file_path, file_checksum)
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS idx_invoice_audit_number
    ON audit.invoice_audit(invoice_number);

CREATE INDEX IF NOT EXISTS idx_invoice_audit_vendor
    ON audit.invoice_audit(vendor_id);

CREATE INDEX IF NOT EXISTS idx_invoice_audit_processed
    ON audit.invoice_audit(processed_at DESC);

CREATE INDEX IF NOT EXISTS idx_line_items_invoice
    ON audit.invoice_line_items(invoice_id);

CREATE INDEX IF NOT EXISTS idx_discrepancies_invoice
    ON audit.discrepancies(invoice_id);

CREATE INDEX IF NOT EXISTS idx_feedback_invoice
    ON audit.human_feedback(invoice_id);

