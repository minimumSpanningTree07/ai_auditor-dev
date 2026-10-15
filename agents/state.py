from typing import Any, Literal, TypedDict








class InvoiceLineItem(TypedDict, total=False):
   # audit.invoice_line_items
   id: int
   invoice_id: str
   line_number: int
   item_code: str | None
   description: str | None
   quantity: float | None
   unit_price: float | None
   line_total: float | None








class Discrepancy(TypedDict, total=False):
   # audit.discrepancies
   id: int
   invoice_id: str
   field_name: str | None
   invoice_value: str | None
   erp_value: str | None
   deviation_pct: float | None
   severity: str | None
   detected_at: str








class HumanFeedback(TypedDict, total=False):
   # audit.human_feedback
   id: int
   invoice_id: str
   field_name: str | None
   original_value: str | None
   corrected_value: str | None
   corrected_by: str | None
   corrected_at: str
   revalidated: bool








class InvoiceState(TypedDict, total=False):
   # Identity and file monitoring
   invoice_id: str
   vendor_id: str | None
   file_path: str | None
   file_checksum: str | None
   file_type: str
   is_duplicate: bool
   duplicate_invoice_id: str | None
   processing_status: str
   error_message: str | None
   retry_count: int




   # Extraction
   extraction_method: str | None
   raw_extracted_text: str | None
   extracted_raw: dict[str, Any]
   extraction_confidence: float | None




   # Language and translation
   source_language: str | None
   detected_script: str | None
   translated_text: str | None
   translation_confidence: float | None




   # Invoice header: audit.invoice_audit
   invoice_number: str | None
   vendor_name: str | None
   po_number: str | None
   invoice_date: str | None
   currency: str | None
   total_amount: float | None
   validation_status: str
   recommendation: Literal[
       "approve", "manual_review", "reject"
   ] | str
   thread_id: str
   processed_at: str | None




   # Audit child tables
   line_items: list[InvoiceLineItem]
   discrepancies: list[Discrepancy]
   human_feedback: list[HumanFeedback]




   # ERP API responses
   erp_vendor: dict[str, Any]
   erp_purchase_order: dict[str, Any]
   erp_sku_data: list[dict[str, Any]]




   # Validation and reporting workflow
   validation_errors: list[str]
   validation_warnings: list[str]
   missing_fields: list[str]
   report: dict[str, Any]
   report_json: dict[str, Any]
   report_summary: str
   report_path: str | None
   report_generated: bool
   report_saved: bool




   # Human review workflow
   human_review_required: bool
   human_decision: dict[str, Any]
   human_review_completed: bool
   revalidation_required: bool




   # LangGraph workflow
   current_stage: str




   # RAG workflow
   question: str | None
   invoice_text: str | None
   report_text: str | None
   documents: list[Any]
   context: str
   answer: str
   relevance: float
   groundedness: float
   context_relevance: float
   score: float
   retries: int


