from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from mock_erp.models import PurchaseOrder, SKU, Vendor
from mock_erp.repository import repository

app = FastAPI(
    title="Mock ERP API",
    version="1.0.0",
)


@app.on_event("startup")
def startup() -> None:
    repository.initialize()


@app.on_event("shutdown")
def shutdown() -> None:
    repository.close()


@app.get("/health")
def health() -> dict[str, bool]:
    return {
        "status": repository.health_check(),
    }


@app.get("/vendor/search", response_model=Vendor)
def search_vendor(
    name: str = Query(..., min_length=1),
) -> Vendor:
    vendor = repository.find_vendor(name)

    if not vendor:
        raise HTTPException(
            status_code=404,
            detail="Vendor not found",
        )

    return vendor


@app.get(
    "/purchase-order/{po_number}",
    response_model=PurchaseOrder,
)
def get_purchase_order(
    po_number: str,
) -> PurchaseOrder:
    purchase_order = repository.get_purchase_order(
        po_number
    )

    if not purchase_order:
        raise HTTPException(
            status_code=404,
            detail="Purchase order not found",
        )

    return purchase_order


@app.get("/sku/{sku_code}", response_model=SKU)
def get_sku(sku_code: str) -> SKU:
    sku = repository.get_sku(sku_code)

    if not sku:
        raise HTTPException(
            status_code=404,
            detail="SKU not found",
        )

    return sku


@app.get("/skus", response_model=list[SKU])
def get_skus(
    codes: str = Query(..., min_length=1),
) -> list[SKU]:
    sku_codes = [
        code.strip()
        for code in codes.split(",")
        if code.strip()
    ]

    return repository.get_skus(sku_codes)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "mock_erp.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )