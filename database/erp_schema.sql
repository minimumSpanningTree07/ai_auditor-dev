
-- Trusted values that matches with the dummy json data
CREATE SCHEMA IF NOT EXISTS erp;

CREATE TABLE IF NOT EXISTS erp.vendors (
    vendor_id VARCHAR(50) PRIMARY KEY,
    vendor_name VARCHAR(255) NOT NULL,
    country VARCHAR(100),
    currency CHAR(3)
);

CREATE TABLE IF NOT EXISTS erp.purchase_orders (
    po_number VARCHAR(64) PRIMARY KEY,
    vendor_id VARCHAR(50) NOT NULL
        REFERENCES erp.vendors(vendor_id)
);

CREATE TABLE IF NOT EXISTS erp.sku_master (
    item_code VARCHAR(64) PRIMARY KEY,
    category VARCHAR(100),
    uom VARCHAR(50),
    gst_rate NUMERIC(5,2)
);

CREATE TABLE IF NOT EXISTS erp.po_line_items (
    id BIGSERIAL PRIMARY KEY,
    po_number VARCHAR(64) NOT NULL
        REFERENCES erp.purchase_orders(po_number),
    item_code VARCHAR(64) NOT NULL
        REFERENCES erp.sku_master(item_code),
    description TEXT,
    qty NUMERIC(12,3) NOT NULL,
    unit_price NUMERIC(14,2) NOT NULL,
    currency CHAR(3) NOT NULL
);
