from fastapi import FastAPI, HTTPException
from database import get_connection

app = FastAPI(title="Mock ERP API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/vendor/{vendor_id}")
def get_vendor(vendor_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM erp.vendors WHERE vendor_id = %s",
                (vendor_id,)
            )
            result = cur.fetchone()

    if result is None:
        raise HTTPException(404, "Vendor not found")
    return result

@app.get("/sku/{item_code}")
def get_sku(item_code:str):
    with get_connection() as con:
        with con.cursor() as cur:
            cur.execute(
                "SELECT * from erp.sku_master where item_code=%s",
                (item_code,)
            )
            result = cur.fetchone()
    if result is None:
        raise HTTPException(404,"ITEM NOT FOUND")
    return result

@app.get("/po/{po_number}")
def get_purchase_order(po_number: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM erp.purchase_orders WHERE po_number = %s",
                (po_number,)
            )
            po = cur.fetchone()
            if po is None:
                raise HTTPException(404, "Purchase order not found")

            cur.execute(
                "SELECT * FROM erp.po_line_items WHERE po_number = %s",
                (po_number,)
            )
            items = cur.fetchall()

    return {"purchase_order": po, "line_items": items}
