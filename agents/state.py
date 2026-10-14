from typing import Any, Literal, TypedDict
from typing_extensions import NotRequired
# ============================================================
# 1. INVOICE LINE ITEMS
# PostgreSQL: audit.invoice_line_items
# ============================================================

class InvoiceLineItem(TypedDict, total=False):
    # PostgreSQL columns
    id: int
    invoice_id: str
    line_number: int
    item_code: str | None
    description: str | None
    quantity: float | None
    unit_price: float | None
    line_total: float | None

    # Intermediate extraction/validation data
    invoice_item_code: str | None
    erp_item_code: str | None
    currency: str | None
    gst_rate: float | None
    validation_status: str | None

# ============================================================
# 2. DISCREPANCIES
# PostgreSQL: audit.discrepancies
# ============================================================

class Discrepancy(TypedDict, total=False):
    # PostgreSQL columns
    id: int
    invoice_id: str
    field_name: str
    invoice_value: str | None
    erp_value: str | None
    deviation_pct: float | None
    severity: str
    detected_at: str

    # Intermediate validation data
    description: str
    discrepancy_type: str
    resolution_status: str

# ============================================================
# 3. HUMAN FEEDBACK
# PostgreSQL: audit.human_feedback
# ============================================================

class HumanFeedback(TypedDict, total=False):
    # PostgreSQL columns
    id: int
    invoice_id: str
    field_name: str
    original_value: str | None
    corrected_value: str | None
    corrected_by: str | None
    corrected_at: str
    revalidated: bool

    # Workflow fields
    decision: Literal["approve", "reject", "correct", "needs_review"]
    comments: str | None


# ============================================================
# 4. COMPLETE LANGGRAPH STATE
# Shared by all nodes in the workflow
# ============================================================
class InvoiceState(TypedDict, total=False):

    # --------------------------------------------------------
    # A. IDENTIFICATION AND FILE MONITORING
    # --------------------------------------------------------

    invoice_id: str
    file_path: str | None
    file_checksum: str | None
    thread_id: str

    is_duplicate: bool
    duplicate_invoice_id: str | None

# --------------------------------------------------------
    # B. DOCUMENT EXTRACTION / OCR
    # --------------------------------------------------------

    extraction_method: Literal[
        "pdfplumber", "docx", "tesseract"
    ] | str | None

    raw_extracted_text: str | None
    extracted_raw: dict[str, Any]
    extraction_confidence: float | None

    # --------------------------------------------------------
    # C. LANGUAGE DETECTION AND TRANSLATION
    # --------------------------------------------------------

    source_language: str | None
    detected_script: str | None
    translated_text: str | None
    translation_confidence: float | None
     # --------------------------------------------------------
    # D. EXTRACTED INVOICE HEADER
    # PostgreSQL: audit.invoice_audit
    # --------------------------------------------------------

    invoice_number: str | None
    vendor_name: str | None
    po_number: str | None
    invoice_date: str | None
    currency: str | None
    total_amount: float | None

    # --------------------------------------------------------
    # E. LINE ITEMS
    # PostgreSQL: audit.invoice_line_items
    # --------------------------------------------------------

    line_items: list[InvoiceLineItem]

     # --------------------------------------------------------
    # F. ERP LOOKUP RESULTS
    # Retrieved through Mock ERP API
    # --------------------------------------------------------

    erp_vendor: dict[str, Any]
    erp_purchase_order: dict[str, Any]
    erp_sku_data: list[dict[str, Any]]

    # --------------------------------------------------------
    # G. VALIDATION RESULTS
    # --------------------------------------------------------

    discrepancies: list[Discrepancy]

    validation_status: Literal[
        "passed", "failed", "partial"
    ] | str

    recommendation: Literal[
        "approve", "review", "reject"
    ] | str

    validation_errors: list[str]
    validation_warnings: list[str]
     # --------------------------------------------------------
    # H. REPORTING
    # --------------------------------------------------------

    report: dict[str, Any]
    report_summary: str
    report_generated: bool
    report_saved: bool

    # --------------------------------------------------------
    # I. HUMAN-IN-THE-LOOP
    # --------------------------------------------------------

    human_review_required: bool
    human_decision: dict[str, Any]
    human_feedback: list[HumanFeedback]
    human_review_completed: bool
    revalidation_required: bool
# --------------------------------------------------------
    # J. WORKFLOW CONTROL / ERROR HANDLING
    # --------------------------------------------------------

    current_stage: str
    processing_status: str
    error_message: str | None
    retry_count: int