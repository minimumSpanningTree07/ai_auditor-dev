"""This tables for auditing"""
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE audit.invoice_audit (
    invoice_id UUID PRIMARY KEY,
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
    thread_id VARCHAR(128),
    processed_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE audit.invoice_line_items (
    id BIGSERIAL PRIMARY KEY,
    invoice_id UUID REFERENCES audit.invoice_audit(invoice_id),
    line_number INTEGER,
    item_code VARCHAR(64),
    description TEXT,
    quantity NUMERIC(12,3),
    unit_price NUMERIC(14,4),
    line_total NUMERIC(14,2)
);
CREATE TABLE audit.discrepancies (
    id BIGSERIAL PRIMARY KEY,
    invoice_id UUID REFERENCES audit.invoice_audit(invoice_id),
    field_name VARCHAR(64),
    invoice_value TEXT,
    erp_value TEXT,
    deviation_pct NUMERIC(8,4),
    severity VARCHAR(16),
    detected_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE audit.human_feedback (
    id BIGSERIAL PRIMARY KEY,
    invoice_id UUID REFERENCES audit.invoice_audit(invoice_id),
    field_name VARCHAR(64),
    original_value TEXT,
    corrected_value TEXT,
    corrected_by VARCHAR(128),
    corrected_at TIMESTAMPTZ DEFAULT now(),
    revalidated BOOLEAN DEFAULT FALSE
);