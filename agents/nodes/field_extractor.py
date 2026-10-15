
import logging
import os
from typing import Any

from pydantic import BaseModel, Field
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import InvoiceState

logger = logging.getLogger(__name__)


# 1. Define the structure of an invoice line item.
class ExtractedLineItem(BaseModel):
    item_code: str | None = None
    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    line_total: float | None = None


# 2. Define the complete invoice extraction schema.
class ExtractedInvoice(BaseModel):
    invoice_number: str | None = None
    vendor_name: str | None = None
    po_number: str | None = None
    invoice_date: str | None = None
    currency: str | None = None
    total_amount: float | None = None
    line_items: list[ExtractedLineItem] = Field(
        default_factory=list
    )


# 3. Configure Amazon Bedrock.
llm = ChatBedrockConverse(
    model=os.getenv(
        "BEDROCK_MODEL_ID",
        "amazon.nova-lite-v1:0",
    ),
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    temperature=0,
    max_tokens=4096,
)

structured_llm = llm.with_structured_output(ExtractedInvoice)


# 4. LangGraph node: extract structured invoice fields.
def extract_invoice_fields(state: InvoiceState) -> dict[str, Any]:
    text = (
        state.get("translated_text")
        or state.get("raw_extracted_text")
        or ""
    ).strip()

    if not text:
        raise ValueError(
            "No invoice text available for field extraction."
        )

    system_prompt = """
Extract invoice data accurately from the provided text or OCR output. Return only valid JSON matching the ExtractedInvoice schema.
Rules:
Extract invoice_number, vendor_name, po_number, invoice_date, currency, and total_amount.
Extract every line item with item_code, description, quantity, unit_price, and line_total.
Preserve item codes and descriptions as printed. Never invent missing values; use null.
Distinguish unit price, line total, subtotal, tax, and final invoice total.
Convert numeric values to numbers and dates to YYYY-MM-DD when unambiguous.
Do not use ERP data to fill missing invoice fields. ERP comparison happens during validation.
Ignore repeated headers and duplicate OCR text.
Return no explanations or additional fields.
Example:
Input:
Invoice: INV-101
Vendor: ABC Supplies
PO: PO-1001
Date: 2026-10-15
Currency: USD

SKU-001 | Wrapping Film | Qty: 50 | Price: 12.00 | Amount: 600.00
Grand Total: 660.00
Output:
{
  "invoice_number": "INV-101",
  "vendor_name": "ABC Supplies",
  "po_number": "PO-1001",
  "invoice_date": "2026-10-15",
  "currency": "USD",
  "total_amount": 660.00,
  "line_items": [
    {
      "item_code": "SKU-001",
      "description": "Wrapping Film",
      "quantity": 50,
      "unit_price": 12.00,
      "line_total": 600.00
    }
  ]
}

"""

    result = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(
            content="Extract the invoice fields from this text:\n\n"
            + text
        ),
    ])

    if not isinstance(result, ExtractedInvoice):
        result = ExtractedInvoice.model_validate(result)

    extracted = result.model_dump()

    # Store the extraction result and populate InvoiceState.
    print("\n")
    print("================================Extracted fields")
    print(f'''invoice_number: {extracted["invoice_number"]},
                  vendor_name: {extracted["vendor_name"]},
                  po_number: {extracted["po_number"]},
                  invoice_date: {extracted["invoice_date"]},
                  currency: {extracted["currency"]},
                  total_amount: {extracted["total_amount"]}''')
    return {
        "invoice_number": extracted["invoice_number"],
        "vendor_name": extracted["vendor_name"],
        "po_number": extracted["po_number"],
        "invoice_date": extracted["invoice_date"],
        "currency": extracted["currency"],
        "total_amount": extracted["total_amount"],
        "line_items": [
            {
                **item,
                "invoice_id": state.get("invoice_id"),
            }
            for item in extracted["line_items"]
        ],
        "extracted_raw": extracted,
        "current_stage": "field_extraction_completed",
    }

