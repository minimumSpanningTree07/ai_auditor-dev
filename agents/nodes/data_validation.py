

from pathlib import Path
from datetime import date
import yaml
from agents.state import InvoiceState
RULES_PATH = Path(__file__).resolve().parent.parent.parent/ "config" / "rules.yaml"








def load_rules():
   with RULES_PATH.open("r", encoding="utf-8") as file:
       return yaml.safe_load(file)








def validate_invoice(state: InvoiceState) -> dict:
   """Check required fields, types, line totals, and tax consistency."""




   rules = load_rules()
   errors = []
   warnings = []




   # Map config names to the names used in InvoiceState.
   header = {
       "invoice_no": state.get("invoice_number"),
       "invoice_date": state.get("invoice_date"),
       "vendor_id": state.get("erp_vendor")or state.get("erp_vendor",{}).get("vendor_id"),
       "currency": state.get("currency"),
       "total_amount": state.get("total_amount"),
   }




   # 1. Check required header fields.
   for field in rules["required_fields"]["header"]:
       value = header.get(field)
       if value is None or str(value).strip() == "":
           errors.append(f"Missing required header field: {field}")




   # 2. Check required line-item fields.
   line_items = state.get("line_items", [])




   if not line_items:
       warnings.append("Invoice contains no line items.")




   for index, item in enumerate(line_items, start=1):
       values = {
           "item_code": item.get("item_code"),
           "description": item.get("description"),
           "qty": item.get("quantity"),
           "unit_price": item.get("unit_price"),
           "total": item.get("line_total"),
       }




       for field in rules["required_fields"]["line_item"]:
           value = values.get(field)
           if value is None or str(value).strip() == "":
               errors.append(
                   f"Line {index}: missing required field '{field}'"
               )




   # 3. Verify that line totals add up to invoice total.
   if line_items and state.get("total_amount") is not None:
       try:
           line_sum = sum(
               float(item["line_total"])
               for item in line_items
               if item.get("line_total") is not None
           )




           invoice_total = float(state["total_amount"])




           if abs(line_sum - invoice_total) > 0.01:
               errors.append(
                   f"Line totals ({line_sum:.2f}) do not match "
                   f"invoice total ({invoice_total:.2f})."
               )
       except (TypeError, ValueError):
           errors.append("Invalid numeric value in invoice or line totals.")




   # 4. Check each line's quantity × unit price against line total.
   for index, item in enumerate(line_items, start=1):
       try:
           qty = item.get("quantity")
           price = item.get("unit_price")
           total = item.get("line_total")




           if qty is not None and price is not None and total is not None:
               expected = float(qty) * float(price)




               if abs(expected - float(total)) > 0.01:
                   errors.append(
                       f"Line {index}: quantity × unit price "
                       f"({expected:.2f}) does not match "
                       f"line total ({float(total):.2f})."
                   )
       except (TypeError, ValueError):
           errors.append(f"Line {index}: invalid numeric values.")




   # 5. Check accepted currency.
   currency = state.get("currency")
   if currency and currency not in rules["accepted_currencies"]:
       errors.append(f"Unsupported currency: {currency}")




   # 6. Check invoice date format/value.
   invoice_date = state.get("invoice_date")
   if invoice_date:
       try:
           date.fromisoformat(str(invoice_date))
       except ValueError:
           errors.append(
               f"Invalid invoice date: {invoice_date}. "
               "Expected YYYY-MM-DD."
           )




   # Return fields that already exist in InvoiceState.
   return {
       "validation_errors": errors,
       "validation_warnings": warnings,
       "validation_status": "failed" if errors else (
           "partial" if warnings else "passed"
       ),
       "current_stage": "data_validation_completed",
   }














