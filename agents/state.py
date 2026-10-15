
from typing import Any, Literal, TypedDict


class InvoiceLineItem(TypedDict, total=False):
    id: int
    invoice_id: str
    line_number: int
    item_code: str | None
    description: str | None
    quantity: float | None
    unit_price: float | None
    line_total: float | None
    invoice_item_code: str | None
    erp_item_code: str | None
    currency: str | None
    gst_rate: float | None
    validation_status: str | None


class Discrepancy(TypedDict, total=False):
    id: int
    invoice_id: str
    field_name: str
    invoice_value: str | None
    erp_value: str | None
    deviation_pct: float | None
    severity: str
    detected_at: str
    description: str
    discrepancy_type: str
    resolution_status: str


class HumanFeedback(TypedDict, total=False):
    id: int
    invoice_id: str
    field_name: str
    original_value: str | None
    corrected_value: str | None
    corrected_by: str | None
    corrected_at: str
    revalidated: bool
    decision: Literal["approve", "reject", "correct", "needs_review"]
    comments: str | None


class InvoiceState(TypedDict, total=False):
    # File monitoring
    invoice_id: str
    file_path: str | None
    file_checksum: str | None
    thread_id: str
    file_type: str
    is_duplicate: bool
    duplicate_invoice_id: str | None

    # Extraction
    raw_extracted_text: str | None
    extraction_method: str | None
    extracted_raw: dict[str, Any]
    extraction_confidence: float | None

    # Language and translation
    source_language: str | None
    detected_script: str | None
    translated_text: str | None
    translation_confidence: float | None

    # Invoice header
    vendor_id:str
    invoice_number: str | None
    vendor_name: str | None
    po_number: str | None
    invoice_date: str | None
    currency: str | None
    total_amount: float | None

    # Line items
    line_items: list[InvoiceLineItem]

    # ERP
    erp_vendor: dict[str, Any]
    erp_purchase_order: dict[str, Any]
    erp_sku_data: list[dict[str, Any]]

    # Validation
    discrepancies: list[Discrepancy]
    validation_status: str
    recommendation: Literal["approve","manual_review","reject"]|str
    validation_errors: list[str]
    validation_warnings: list[str]

    # Reporting
    report: dict[str, Any]
    report_summary: str
    report_generated: bool
    report_saved: bool
    missing_fields:list[str]

    # Human review
    human_review_required: bool
    human_decision: dict[str, Any]
    human_feedback: list[HumanFeedback]
    human_review_completed: bool
    revalidation_required: bool

    # Workflow
    current_stage: str
    processing_status: str
    error_message: str | None
    retry_count: int

    # RAG input
    question: str | None
    invoice_text: str | None
    report_text: str | None

    # RAG processing
    documents: list[Any]
    context: str
    answer: str
    relevance: float
    groundedness: float
    context_relevance: float
    score: float
    retries: int

