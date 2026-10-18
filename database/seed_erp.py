"""Idempotently seed the canonical ERP schema from data/ERP_mockdata JSON."""
import json
import os
from pathlib import Path
import psycopg

DATA_DIR = Path(os.getenv("ERP_MOCKDATA_DIR", str(Path(__file__).resolve().parent.parent / "data" / "ERP_mockdata")))

def load_json(filename: str):
    with (DATA_DIR / filename).open(encoding="utf-8") as file:
        return json.load(file)

def seed() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for vendor in load_json("vendors.json"):
                vendor_id = vendor["vendor_id"]
                cur.execute(
                    """INSERT INTO erp.vendors
                       (vendor_id, vendor_code, vendor_name, country, currency, active)
                       VALUES (%s, %s, %s, %s, %s, TRUE)
                       ON CONFLICT (vendor_id) DO UPDATE SET
                         vendor_name=EXCLUDED.vendor_name, country=EXCLUDED.country,
                         currency=EXCLUDED.currency, active=EXCLUDED.active""",
                    (vendor_id, vendor.get("vendor_code", vendor_id),
                     vendor["vendor_name"], vendor.get("country"), vendor.get("currency", "USD")),
                )

            for item in load_json("sku_master.json"):
                sku = item.get("sku") or item.get("item_code")
                if not sku:
                    continue
                description = item.get("description") or item.get("category") or sku
                cur.execute(
                    """INSERT INTO erp.skus (sku, description, unit_of_measure, active)
                       VALUES (%s, %s, %s, TRUE)
                       ON CONFLICT (sku) DO UPDATE SET
                         description=EXCLUDED.description,
                         unit_of_measure=EXCLUDED.unit_of_measure, active=EXCLUDED.active""",
                    (sku, description, item.get("unit_of_measure") or item.get("uom")),
                )

            for po in load_json("purchase_orders.json"):
                vendor_id = po["vendor_id"]
                cur.execute("SELECT vendor_name, currency FROM erp.vendors WHERE vendor_id=%s", (vendor_id,))
                vendor = cur.fetchone()
                if not vendor:
                    raise ValueError(f"Unknown vendor {vendor_id} for PO {po['po_number']}")
                vendor_name, vendor_currency = vendor
                currency = po.get("currency") or vendor_currency or "USD"
                cur.execute(
                    """INSERT INTO erp.purchase_orders
                       (po_number, vendor_id, vendor_name, order_date, currency, status)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (po_number) DO UPDATE SET
                         vendor_id=EXCLUDED.vendor_id, vendor_name=EXCLUDED.vendor_name,
                         order_date=EXCLUDED.order_date, currency=EXCLUDED.currency, status=EXCLUDED.status""",
                    (po["po_number"], vendor_id, vendor_name, po.get("order_date"), currency, po.get("status", "OPEN")),
                )
                for idx, item in enumerate(po.get("line_items", []), start=1):
                    sku = item.get("sku") or item.get("item_code")
                    if not sku:
                        continue
                    quantity = item.get("quantity", item.get("qty", 0))
                    cur.execute(
                        """INSERT INTO erp.purchase_order_lines
                           (po_number, line_number, sku, description, quantity, unit_price, currency)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (po_number, line_number) DO UPDATE SET
                             sku=EXCLUDED.sku, description=EXCLUDED.description,
                             quantity=EXCLUDED.quantity, unit_price=EXCLUDED.unit_price, currency=EXCLUDED.currency""",
                        (po["po_number"], item.get("line_number", idx), sku, item.get("description", ""),
                         quantity, item.get("unit_price", 0), item.get("currency", currency)),
                    )
    print("ERP seed completed successfully.")

if __name__ == "__main__":
    seed()
