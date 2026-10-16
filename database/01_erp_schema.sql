CREATE SCHEMA IF NOT EXISTS erp;

CREATE TABLE IF NOT EXISTS erp.vendors (
    vendor_id VARCHAR(64) PRIMARY KEY,
    vendor_code VARCHAR(64) UNIQUE,
    vendor_name VARCHAR(255) NOT NULL,
    currency VARCHAR(16),
    country VARCHAR(128),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS erp.purchase_orders (
    po_number VARCHAR(64) PRIMARY KEY,
    vendor_id VARCHAR(64) NOT NULL
        REFERENCES erp.vendors(vendor_id),
    vendor_name VARCHAR(255) NOT NULL,
    order_date DATE,
    currency VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN'
);

CREATE TABLE IF NOT EXISTS erp.purchase_order_lines (
    id BIGSERIAL PRIMARY KEY,
    po_number VARCHAR(64) NOT NULL
        REFERENCES erp.purchase_orders(po_number)
        ON DELETE CASCADE,
    line_number INTEGER NOT NULL,
    sku VARCHAR(128) NOT NULL,
    description TEXT,
    quantity NUMERIC(18, 4) NOT NULL,
    unit_price NUMERIC(18, 4) NOT NULL,
    currency VARCHAR(16),
    UNIQUE (po_number, line_number)
);

CREATE TABLE IF NOT EXISTS erp.skus (
    sku VARCHAR(128) PRIMARY KEY,
    description TEXT NOT NULL,
    unit_of_measure VARCHAR(32),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_erp_vendors_name
    ON erp.vendors (LOWER(vendor_name));

CREATE INDEX IF NOT EXISTS idx_erp_po_vendor
    ON erp.purchase_orders (vendor_id);

CREATE INDEX IF NOT EXISTS idx_erp_po_lines_po
    ON erp.purchase_order_lines (po_number);

CREATE INDEX IF NOT EXISTS idx_erp_po_lines_sku
    ON erp.purchase_order_lines (sku);