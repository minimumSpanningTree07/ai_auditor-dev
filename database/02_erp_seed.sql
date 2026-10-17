
BEGIN;

CREATE SCHEMA IF NOT EXISTS erp;

-- 1. Vendor master
CREATE TABLE IF NOT EXISTS erp.vendors (
    vendor_id   VARCHAR(50) PRIMARY KEY,
    vendor_name TEXT NOT NULL,
    country     TEXT,
    currency    VARCHAR(3) NOT NULL
);

-- 2. SKU master
CREATE TABLE IF NOT EXISTS erp.sku_master (
    item_code VARCHAR(50) PRIMARY KEY,
    category  TEXT,
    uom       TEXT,
    gst_rate  NUMERIC(5,2) NOT NULL DEFAULT 0
);

-- 3. Purchase order headers
CREATE TABLE IF NOT EXISTS erp.purchase_orders (
    po_number VARCHAR(50) PRIMARY KEY,
    vendor_id VARCHAR(50) NOT NULL
        REFERENCES erp.vendors(vendor_id)
);

-- 4. Purchase order line items
CREATE TABLE IF NOT EXISTS erp.purchase_order_lines (
    po_number  VARCHAR(50) NOT NULL
        REFERENCES erp.purchase_orders(po_number)
        ON DELETE CASCADE,
    item_code  VARCHAR(50) NOT NULL
        REFERENCES erp.sku_master(item_code),
    description TEXT NOT NULL,
    qty         NUMERIC(14,3) NOT NULL,
    unit_price  NUMERIC(14,2) NOT NULL,
    currency    VARCHAR(3) NOT NULL,
    PRIMARY KEY (po_number, item_code)
);

-- Seed vendors
INSERT INTO erp.vendors
    (vendor_id, vendor_name, country, currency)
VALUES
    ('VEND-001', 'Global Logistics Ltd', 'UK', 'USD'),
    ('VEND-002', 'BlueOcean Transport Co.', 'USA', 'USD'),
    ('VEND-003', 'Transporte Ibérico S.A.', 'Spain', 'EUR'),
    ('VEND-004', 'HafenLogistik GmbH', 'Germany', 'EUR'),
    ('VEND-005', 'SwiftMove Couriers', 'USA', 'USD'),
    ('VEND-006', 'OceanFreight Pvt Ltd', 'India', 'INR')
ON CONFLICT (vendor_id) DO UPDATE SET
    vendor_name = EXCLUDED.vendor_name,
    country = EXCLUDED.country,
    currency = EXCLUDED.currency;

-- Seed SKUs
INSERT INTO erp.sku_master
    (item_code, category, uom, gst_rate)
VALUES
    ('SKU-001', 'Packaging', 'roll', 10),
    ('SKU-002', 'Safety', 'pair', 10),
    ('SKU-003', 'Safety', 'piece', 10),
    ('SKU-101', 'Logistics', 'piece', 10),
    ('SKU-201', 'Packaging', 'box', 10),
    ('SKU-202', 'Packaging', 'label', 10),
    ('SKU-301', 'Transport', 'crate', 10),
    ('SKU-302', 'Safety', 'vest', 10),
    ('SKU-401', 'Charges', 'service', 10),
    ('SKU-402', 'Packaging', 'box', 10),
    ('SKU-501', 'Transport', 'service', 10)
ON CONFLICT (item_code) DO UPDATE SET
    category = EXCLUDED.category,
    uom = EXCLUDED.uom,
    gst_rate = EXCLUDED.gst_rate;

-- Seed purchase order headers
INSERT INTO erp.purchase_orders (po_number, vendor_id)
VALUES
    ('PO-1001', 'VEND-001'),
    ('PO-1002', 'VEND-002'),
    ('PO-1003', 'VEND-003'),
    ('PO-1004', 'VEND-004'),
    ('PO-1005', 'VEND-005'),
    ('PO-1006', 'VEND-006')
ON CONFLICT (po_number) DO UPDATE SET
    vendor_id = EXCLUDED.vendor_id;

-- Seed purchase order lines
INSERT INTO erp.purchase_order_lines
    (po_number, item_code, description, qty, unit_price, currency)
VALUES
    ('PO-1001', 'SKU-001', 'Pallet Wrapping Film', 50, 12.00, 'USD'),
    ('PO-1001', 'SKU-002', 'Industrial Gloves', 120, 3.00, 'USD'),
    ('PO-1001', 'SKU-003', 'Safety Helmets', 30, 15.00, 'USD'),

    ('PO-1002', 'SKU-101', 'Container Seals', 200, 1.25, 'USD'),

    ('PO-1003', 'SKU-201', 'Cajas de carton', 100, 2.50, 'EUR'),
    ('PO-1003', 'SKU-202', 'Etiquetas adhesivas', 300, 0.30, 'EUR'),

    ('PO-1004', 'SKU-301', 'Transportkisten', 40, 25.00, 'EUR'),
    ('PO-1004', 'SKU-302', 'Sicherheitswesten', 60, 10.00, 'EUR'),

    ('PO-1005', 'SKU-401', 'Fuel Surcharge', 1, 120.00, 'USD'),
    ('PO-1005', 'SKU-402', 'Express Delivery Boxes', 25, 4.50, 'USD'),

    ('PO-1006', 'SKU-501', 'Container Transport', 5, 8000.00, 'INR')
ON CONFLICT (po_number, item_code) DO UPDATE SET
    description = EXCLUDED.description,
    qty = EXCLUDED.qty,
    unit_price = EXCLUDED.unit_price,
    currency = EXCLUDED.currency;

COMMIT;
