# Human review improvements

- The Human review tab now loads the purchase order from the mock ERP and shows invoice-extracted line values alongside ERP line values, including SKU, description, quantity, unit price and currency.
- Line-item correction controls allow SKU, quantity and unit-price edits. Only changed values are sent to revalidation; the audit still needs the source invoice and purchase order to support a final decision.
- “Save feedback note only” records a human note without rerunning extraction/validation or changing invoice values.
- Streamlit form controls force a high-contrast light input surface with dark text and readable placeholders, regardless of browser/app theme.
- UI connects to ERP through `ERP_URL=http://mock-erp:8000` in Compose.

The ERP purchase-order API is read-only. Corrections update the audited invoice's effective values; they do not modify the ERP purchase order itself.
