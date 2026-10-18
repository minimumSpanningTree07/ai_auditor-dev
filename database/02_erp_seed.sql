BEGIN;

CREATE SCHEMA IF NOT EXISTS erp;

-- This seed uses the canonical tables/columns defined in 01_erp_schema.sql.
INSERT INTO erp.vendors (vendor_id, vendor_code, vendor_name, currency, country, active)
VALUES
    ('VEND-001', 'VEND-001', 'Global Logistics Ltd', 'USD', 'UK', TRUE),
    ('VEND-002', 'VEND-002', 'BlueOcean Transport Co.', 'USD', 'USA', TRUE),
    ('VEND-003', 'VEND-003', 'Transporte Ibérico S.A.', 'EUR', 'Spain', TRUE),
    ('VEND-004', 'VEND-004', 'HafenLogistik GmbH', 'EUR', 'Germany', TRUE),
    ('VEND-005', 'VEND-005', 'SwiftMove Couriers', 'USD', 'USA', TRUE),
    ('VEND-006', 'VEND-006', 'OceanFreight Pvt Ltd', 'INR', 'India', TRUE)
ON CONFLICT (vendor_id) DO UPDATE SET
    vendor_code = EXCLUDED.vendor_code,
    vendor_name = EXCLUDED.vendor_name,
    currency = EXCLUDED.currency,
    country = EXCLUDED.country,
    active = EXCLUDED.active;

INSERT INTO erp.skus (sku, description, unit_of_measure, active)
VALUES
    ('SKU-001', 'Pallet Wrapping Film', 'roll', TRUE),
    ('SKU-002', 'Industrial Gloves', 'pair', TRUE),
    ('SKU-003', 'Safety Helmets', 'piece', TRUE),
    ('SKU-101', 'Container Seals', 'piece', TRUE),
    ('SKU-201', 'Cajas de carton', 'box', TRUE),
    ('SKU-202', 'Etiquetas adhesivas', 'label', TRUE),
    ('SKU-301', 'Transportkisten', 'crate', TRUE),
    ('SKU-302', 'Sicherheitswesten', 'vest', TRUE),
    ('SKU-401', 'Fuel Surcharge', 'service', TRUE),
    ('SKU-402', 'Express Delivery Boxes', 'box', TRUE),
    ('SKU-501', 'Container Transport', 'service', TRUE)
ON CONFLICT (sku) DO UPDATE SET
    description = EXCLUDED.description,
    unit_of_measure = EXCLUDED.unit_of_measure,
    active = EXCLUDED.active;

INSERT INTO erp.purchase_orders
    (po_number, vendor_id, vendor_name, order_date, currency, status)
VALUES
    ('PO-1001', 'VEND-001', 'Global Logistics Ltd', DATE '2026-01-01', 'USD', 'OPEN'),
    ('PO-1002', 'VEND-002', 'BlueOcean Transport Co.', DATE '2026-01-02', 'USD', 'OPEN'),
    ('PO-1003', 'VEND-003', 'Transporte Ibérico S.A.', DATE '2026-01-03', 'EUR', 'OPEN'),
    ('PO-1004', 'VEND-004', 'HafenLogistik GmbH', DATE '2026-01-04', 'EUR', 'OPEN'),
    ('PO-1005', 'VEND-005', 'SwiftMove Couriers', DATE '2026-01-05', 'USD', 'OPEN'),
    ('PO-1006', 'VEND-006', 'OceanFreight Pvt Ltd', DATE '2026-01-06', 'INR', 'OPEN')
ON CONFLICT (po_number) DO UPDATE SET
    vendor_id = EXCLUDED.vendor_id,
    vendor_name = EXCLUDED.vendor_name,
    order_date = EXCLUDED.order_date,
    currency = EXCLUDED.currency,
    status = EXCLUDED.status;

INSERT INTO erp.purchase_order_lines
    (po_number, line_number, sku, description, quantity, unit_price, currency)
VALUES
    ('PO-1001', 1, 'SKU-001', 'Pallet Wrapping Film', 50, 12.00, 'USD'),
    ('PO-1001', 2, 'SKU-002', 'Industrial Gloves', 120, 3.00, 'USD'),
    ('PO-1001', 3, 'SKU-003', 'Safety Helmets', 30, 15.00, 'USD'),
    ('PO-1002', 1, 'SKU-101', 'Container Seals', 200, 1.25, 'USD'),
    ('PO-1003', 1, 'SKU-201', 'Cajas de carton', 100, 2.50, 'EUR'),
    ('PO-1003', 2, 'SKU-202', 'Etiquetas adhesivas', 300, 0.30, 'EUR'),
    ('PO-1004', 1, 'SKU-301', 'Transportkisten', 40, 25.00, 'EUR'),
    ('PO-1004', 2, 'SKU-302', 'Sicherheitswesten', 60, 10.00, 'EUR'),
    ('PO-1005', 1, 'SKU-401', 'Fuel Surcharge', 1, 120.00, 'USD'),
    ('PO-1005', 2, 'SKU-402', 'Express Delivery Boxes', 25, 4.50, 'USD'),
    ('PO-1006', 1, 'SKU-501', 'Container Transport', 5, 8000.00, 'INR')
ON CONFLICT (po_number, line_number) DO UPDATE SET
    sku = EXCLUDED.sku,
    description = EXCLUDED.description,
    quantity = EXCLUDED.quantity,
    unit_price = EXCLUDED.unit_price,
    currency = EXCLUDED.currency;

COMMIT;
