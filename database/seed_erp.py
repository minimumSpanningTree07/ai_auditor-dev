"""This file reads the json files from mockdata and inserts into the 
erp tables """
import json
import os
from pathlib import Path
import psycopg


DATA_DIR = Path(
    os.getenv("ERP_MOCKDATA_DIR", "/app/erp_mockdata")
)

#Helper function
def load_json(filename):
    with open(DATA_DIR / filename, encoding="utf-8") as file:
        return json.load(file)

def seed():
    #create connection and cursor objects
    with psycopg.connect(os.getenv("DATABASE_URL")) as conn:
        with conn.cursor() as cur:
             # Insert vendors first
            for vendor in load_json("vendors.json"):
                cur.execute("""
                    INSERT INTO erp.vendors
                        (vendor_id, vendor_name, country, currency)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (vendor_id) DO NOTHING
                """, (
                    vendor["vendor_id"],
                    vendor["vendor_name"],
                    vendor.get("country"),
                    vendor.get("currency"),
                ))

            # Insert SKU master data
            for sku in load_json("sku_master.json"):
                cur.execute("""
                    INSERT INTO erp.sku_master
                        (item_code, category, uom, gst_rate)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (item_code) DO NOTHING
                """, (
                    sku["item_code"],
                    sku.get("category"),
                    sku.get("uom"),
                    sku.get("gst_rate"),
                ))

            # Insert purchase orders and their line items
            for po in load_json("purchase_orders.json"):
                cur.execute("""
                    INSERT INTO erp.purchase_orders
                        (po_number, vendor_id)
                    VALUES (%s, %s)
                    ON CONFLICT (po_number) DO NOTHING
                """, (po["po_number"], po["vendor_id"]))

                for item in po["line_items"]:
                    cur.execute("""
                        INSERT INTO erp.po_line_items
                            (po_number, item_code, description,
                             qty, unit_price, currency)
                        SELECT %s, %s, %s, %s, %s, %s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM erp.po_line_items
                            WHERE po_number = %s AND item_code = %s
                        )
                    """, (
                        po["po_number"],
                        item["item_code"],
                        item["description"],
                        item["qty"],
                        item["unit_price"],
                        item["currency"],
                        po["po_number"],
                        item["item_code"],
                    ))

        print("ERP dummy data inserted successfully.")





if __name__ == "__main__":
    seed()