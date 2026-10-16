from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class Vendor(BaseModel):
    vendor_id: str
    vendor_code: str | None = None
    vendor_name: str
    currency: str | None = None
    country: str | None = None
    active: bool = True


class PurchaseOrderLine(BaseModel):
    line_number: int
    sku: str
    description: str | None = None
    quantity: Decimal
    unit_price: Decimal
    currency: str | None = None

    @property
    def line_total(self) -> Decimal:
        return self.quantity * self.unit_price


class PurchaseOrder(BaseModel):
    po_number: str
    vendor_id: str
    vendor_name: str
    order_date: date | None = None
    currency: str
    status: str = "OPEN"
    line_items: list[PurchaseOrderLine] = Field(
        default_factory=list
    )


class SKU(BaseModel):
    sku: str
    description: str
    unit_of_measure: str | None = None
    active: bool = True