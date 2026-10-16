from __future__ import annotations

from typing import Any, TypedDict


class InvoiceState(TypedDict, total=False):
    """
    Shared state for the invoice-auditing LangGraph workflow.

    All invoice-processing nodes communicate through this state.

    Important:
    - Original extraction values are never overwritten by human feedback.
    - ERP information comes from the Mock ERP service.
    - Validation operates on the effective values.
    """

    # ============================================================
    # WORKFLOW
    # ============================================================

    workflow_mode: str
    """
    Examples:
        "invoice"
        "revalidation"
        "query"
    """

    thread_id: str

    invoice_id: str

    force_revalidation: bool

    # ============================================================
    # FILE / DOCUMENT
    # ============================================================

    file_path: str

    file_name: str

    file_type: str

    file_checksum: str

    file_size: int

    is_duplicate: bool

    # ============================================================
    # DOCUMENT EXTRACTION
    # ============================================================

    extraction_method: str
    """
    Examples:
        "text"
        "ocr"
        "text+ocr"
    """

    raw_extracted_text: str

    extraction_confidence: float

    extraction_errors: list[str]

    # ============================================================
    # LANGUAGE / TRANSLATION
    # ============================================================

    source_language: str

    translated_text: str

    translation_used: bool

    translation_confidence: float

    translation_error: str

    # ============================================================
    # ORIGINAL AI EXTRACTION
    # ============================================================
    #
    # These values represent what the AI/document extractor
    # originally extracted.
    #
    # Human corrections MUST NOT overwrite these fields.
    #

    extracted_invoice_number: str

    extracted_vendor_name: str

    extracted_po_number: str

    extracted_invoice_date: str

    extracted_currency: str

    extracted_subtotal_amount: float

    extracted_tax_amount: float

    extracted_tax_rate: float

    extracted_total_amount: float

    extracted_line_items: list[dict[str, Any]]

    # ============================================================
    # EFFECTIVE VALUES
    # ============================================================
    #
    # These are the values used during validation.
    #
    # Initially they come from the extracted_* fields.
    # If a human correction exists, the corrected value is used
    # here while the original extraction remains untouched.
    #

    invoice_number: str

    vendor_name: str

    vendor_id: str

    po_number: str

    invoice_date: str

    currency: str

    subtotal_amount: float

    tax_amount: float

    tax_rate: float

    total_amount: float

    line_items: list[dict[str, Any]]

    # ============================================================
    # HUMAN FEEDBACK
    # ============================================================

    human_feedback: list[dict[str, Any]]

    human_corrections: dict[str, Any]

    human_decision: str
    """
    Examples:
        "approved"
        "rejected"
        "corrected"
    """

    # ============================================================
    # ERP DATA
    # ============================================================

    erp_vendor: dict[str, Any]

    erp_purchase_order: dict[str, Any]

    erp_line_items: list[dict[str, Any]]

    erp_skus: list[dict[str, Any]]

    # ============================================================
    # BUSINESS VALIDATION
    # ============================================================

    vendor_match: bool

    po_match: bool

    currency_match: bool

    sku_match: bool

    quantity_match: bool

    unit_price_match: bool

    business_validation_passed: bool

    business_validation_errors: list[str]

    business_validation_warnings: list[str]

    # ============================================================
    # DATA VALIDATION
    # ============================================================

    required_fields_valid: bool

    line_totals_valid: bool

    subtotal_valid: bool

    tax_valid: bool

    total_valid: bool

    date_valid: bool

    currency_valid: bool

    data_validation_passed: bool

    data_validation_errors: list[str]

    data_validation_warnings: list[str]

    # ============================================================
    # DISCREPANCIES
    # ============================================================

    discrepancies: list[dict[str, Any]]

    missing_fields: list[str]

    validation_errors: list[str]

    validation_warnings: list[str]

    # ============================================================
    # FINAL AUDIT DECISION
    # ============================================================

    validation_status: str
    """
    Examples:
        "passed"
        "failed"
        "manual_review"
        "duplicate"
    """

    recommendation: str
    """
    Examples:
        "approve"
        "reject"
        "manual_review"
    """

    human_review_required: bool

    audit_score: float

    # ============================================================
    # REPORT
    # ============================================================

    report: dict[str, Any]

    report_path: str

    report_summary: str

    # ============================================================
    # DATABASE
    # ============================================================

    persistence_status: str

    persistence_error: str

    # ============================================================
    # RAG / QUERY
    # ============================================================

    question: str

    query_intent: str
    """
    Examples:
        "structured"
        "semantic"
    """

    query_filters: dict[str, Any]

    retrieved_documents: list[dict[str, Any]]

    augmented_context: str

    rag_answer: str

    rag_context_relevance: float

    rag_answer_groundedness: float

    rag_question_relevance: float

    rag_triad_score: float

    rag_retry_count: int

    # ============================================================
    # ERRORS / CONTROL FLOW
    # ============================================================

    errors: list[str]

    warnings: list[str]

    processing_status: str
    """
    Examples:
        "queued"
        "processing"
        "completed"
        "failed"
        "manual_review"
    """