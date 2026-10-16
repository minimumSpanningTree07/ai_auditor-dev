INSERT INTO erp.vendors (
    vendor_id,
    vendor_code,
    vendor_name,
    currency,
    country,
    active
)
VALUES
    (
        'V001',
        'GL-001',
        'Global Logistics Ltd',
        'USD',
        'USA',
        TRUE
    ),
    (
        'V002',
        'AC-002',
        'Acme Corporation',
        'USD',
        'USA',
        TRUE
    ),
    (
        'V003',
        'TS-003',
        'Tech Supplies Pvt Ltd',
        'INR',
        'India',
        TRUE
    )
ON CONFLICT (vendor_id) DO UPDATE
SET
    vendor_code = EXCLUDED.vendor_code,
    vendor_name = EXCLUDED.vendor_name,
    currency = EXCLUDED.currency,
    country = EXCLUDED.country,
    active = EXCLUDED.active;


INSERT INTO erp.skus (
    sku,
    description,
    unit_of_measure,
    active
)
VALUES
    (
        'SKU-001',
        'Industrial Equipment',
        'EA',
        TRUE
    ),
    (
        'SKU-002',
        'Packaging Material',
        'EA',
        TRUE
    ),
    (
        'SKU-003',
        'Logistics Service',
        'EA',
        TRUE
    ),
    (
        'SKU-004',
        'Maintenance Service',
        'EA',
        TRUE
    )
ON CONFLICT (sku) DO UPDATE
SET
    description = EXCLUDED.description,
    unit_of_measure = EXCLUDED.unit_of_measure,
    active = EXCLUDED.active;


INSERT INTO erp.purchase_orders (
    po_number,
    vendor_id,
    vendor_name,
    order_date,
    currency,
    status
)
VALUES
    (
        'PO-1001',
        'V001',
        'Global Logistics Ltd',
        '2025-03-01',
        'USD',
        'OPEN'
    ),
    (
        'PO-1002',
        'V002',
        'Acme Corporation',
        '2025-03-05',
        'USD',
        'OPEN'
    ),
    (
        'PO-1003',
        'V003',
        'Tech Supplies Pvt Ltd',
        '2025-03-10',
        'INR',
        'OPEN'
    )
ON CONFLICT (po_number) DO UPDATE
SET
    vendor_id = EXCLUDED.vendor_id,
    vendor_name = EXCLUDED.vendor_name,
    order_date = EXCLUDED.order_date,
    currency = EXCLUDED.currency,
    status = EXCLUDED.status;


INSERT INTO erp.purchase_order_lines (
    po_number,
    line_number,
    sku,
    description,
    quantity,
    unit_price,
    currency
)
VALUES
    (
        'PO-1001',
        1,
        'SKU-001',
        'Industrial Equipment',
        10,
        100.00,
        'USD'
    ),
    (
        'PO-1001',
        2,
        'SKU-003',
        'Logistics Service',
        7,
        70.00,
        'USD'
    ),

    (
        'PO-1002',
        1,
        'SKU-002',
        'Packaging Material',
        20,
        50.00,
        'USD'
    ),
    (
        'PO-1002',
        2,
        'SKU-004',
        'Maintenance Service',
        5,
        100.00,
        'USD'
    ),

    (
        'PO-1003',
        1,
        'SKU-001',
        'Industrial Equipment',
        8,
        10000.00,
        'INR'
    ),
    (
        'PO-1003',
        2,
        'SKU-002',
        'Packaging Material',
        10,
        500.00,
        'INR'
    )
ON CONFLICT (po_number, line_number) DO UPDATE
SET
    sku = EXCLUDED.sku,
    description = EXCLUDED.description,
    quantity = EXCLUDED.quantity,
    unit_price = EXCLUDED.unit_price,
    currency = EXCLUDED.currency;