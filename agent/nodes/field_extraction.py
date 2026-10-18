
from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from litellm import completion
from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent.config import settings


# ---------------------------------------------------------------------
# Structured extraction models
# ---------------------------------------------------------------------

class InvoiceLine(BaseModel):
    model_config = ConfigDict(extra="ignore")

    item_code: str | None = None
    description: str | None = None
    quantity: Decimal | None = None
    unit_of_measure: str | None = None
    unit_price: Decimal | None = None
    line_total: Decimal | None = None
    currency: str | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def clean_line_currency(cls, value: Any) -> Any:
        if value is None:
            return None

        cleaned = str(value).strip().upper()

        currency_map = {
            "$": "USD",
            "US$": "USD",
            "USD": "USD",
            "€": "EUR",
            "EUR": "EUR",
            "£": "GBP",
            "GBP": "GBP",
            "₹": "INR",
            "RS": "INR",
            "RS.": "INR",
            "INR": "INR",
            "₫": "VND",
            "VND": "VND",
        }

        return currency_map.get(cleaned, cleaned) or None


class ExtractedInvoice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_type: Literal[
        "invoice",
        "debit_note",
        "credit_note",
        "unknown",
    ] = "unknown"

    vendor_name: str | None = None
    vendor_address: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    po_number: str | None = None
    currency: str | None = None

    line_items: list[InvoiceLine] = Field(default_factory=list)

    subtotal: Decimal | None = None
    tax_rate_percent: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal | None = None

    original_text: str = ""
    translated_text: str = ""

    missing_fields: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)

    @field_validator(
        "vendor_name",
        "vendor_address",
        "invoice_number",
        "po_number",
        mode="before",
    )
    @classmethod
    def clean_text_fields(cls, value: Any) -> Any:
        if value is None:
            return None

        cleaned = str(value).strip()
        return cleaned or None

    # @field_validator("currency", mode="before")
    # @classmethod
    # def clean_currency(cls, value: Any) -> Any:
    #     if value is None:
    #         return None

    #     cleaned = str(value).strip().upper()
    #     return cleaned or None
    @field_validator("currency", mode="before")
    @classmethod
    def clean_currency(cls, value: Any) -> Any:
        if value is None:
            return None

        cleaned = str(value).strip().upper()

        currency_map = {
            "$": "USD",
            "US$": "USD",
            "USD": "USD",
            "€": "EUR",
            "EUR": "EUR",
            "£": "GBP",
            "GBP": "GBP",
            "₹": "INR",
            "RS": "INR",
            "RS.": "INR",
            "INR": "INR",
            "₫": "VND",
            "VND": "VND",
        }

        return currency_map.get(cleaned, cleaned) or None


FIELD_EXTRACTION_PROMPT = """
Extract structured information from a supplier invoice, debit note,
or credit note.

Use the original OCR text and translated text together. The original
text is the source evidence. The translated text may help interpret
the original, but must not override identifiers, amounts, dates,
quantities, or product codes that are clearly present in the original.

Return one valid JSON object only, with these fields:

{
  "document_type": "invoice | debit_note | credit_note | unknown",
  "vendor_name": null,
  "vendor_address": null,
  "invoice_number": null,
  "invoice_date": null,
  "po_number": null,
  "currency": null,
  "line_items": [
    {
      "item_code": null,
      "description": null,
      "quantity": null,
      "unit_of_measure": null,
      "unit_price": null,
      "line_total": null,
      "currency": null
    }
  ],
  "subtotal": null,
  "tax_rate_percent": null,
  "tax_amount": null,
  "total_amount": null,
  "missing_fields": [],
  "review_reasons": []
}

Rules:
- Do not invent missing values. Use null when a value cannot be
  determined from the document.
- Keep invoice numbers, PO numbers, and item codes exactly as printed,
  apart from trimming surrounding whitespace.
- Use ISO format YYYY-MM-DD for invoice_date when unambiguous.
- Return numeric values as JSON numbers or numeric strings without
  currency symbols or thousands separators.
- Do not confuse subtotal, tax amount, and total amount.
- tax_rate_percent is the percentage value, for example 18 for 18%.
- Each line item should represent one invoice line.
- Preserve negative values and signs when present.
- Do not infer that a vendor, PO, or SKU exists in the ERP.
- Add uncertain or conflicting information to review_reasons.
- Include important missing fields in missing_fields.
- Do not include markdown fences or explanatory text.
"""


# ---------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------

def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None

    if isinstance(value, Decimal):
        return value

    try:
        cleaned = str(value).strip().replace(",", "")
        cleaned = re.sub(r"^[^\d+\-.]+", "", cleaned)
        cleaned = re.sub(r"[^\d.\-+]+$", "", cleaned)

        if not cleaned:
            return None

        return Decimal(cleaned)
    except (InvalidOperation, ValueError, TypeError):
        return None


def normalize_sku(value: Any) -> str | None:
    if value is None:
        return None

    normalized = re.sub(r"\s+", "", str(value)).strip()
    return normalized or None


def _parse_model_response(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content

    if not isinstance(content, str) or not content.strip():
        raise ValueError("The LLM returned an empty extraction response.")

    text = content.strip()

    # Accommodate providers that return JSON inside markdown fences.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"The LLM response was not valid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError("The LLM response must be a JSON object.")

    return parsed


def extract_invoice_fields(
    original_text: str,
    translated_text: str,
) -> ExtractedInvoice:
    """
    Extract invoice fields using the configured LiteLLM model.

    This function performs extraction only. ERP lookups and validation
    are handled by their respective workflow nodes.
    """
    original_text = original_text or ""
    translated_text = translated_text or original_text

    if not original_text.strip() and not translated_text.strip():
        raise ValueError("No invoice text is available for field extraction.")

    response = completion(
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": FIELD_EXTRACTION_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    "ORIGINAL OCR TEXT:\n"
                    f"{original_text}\n\n"
                    "TRANSLATED TEXT:\n"
                    f"{translated_text}"
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=settings.llm_max_tokens,
    )

    content = response.choices[0].message.content
    data = _parse_model_response(content)

    data["original_text"] = original_text
    data["translated_text"] = translated_text

    invoice = ExtractedInvoice.model_validate(data)
    return finalize_extraction(
        invoice,
        original_text=original_text,
        translated_text=translated_text,
    )


# ---------------------------------------------------------------------
# Arithmetic consistency checks
# ---------------------------------------------------------------------

def check_invoice_consistency(
    invoice: ExtractedInvoice,
    tolerance: Decimal = Decimal("0.02"),
) -> list[str]:
    issues: list[str] = []
    line_totals: list[Decimal] = []

    for index, item in enumerate(invoice.line_items, start=1):
        if item.quantity is not None and item.quantity < 0:
            issues.append(f"Line {index}: quantity is negative.")

        if item.unit_price is not None and item.unit_price < 0:
            issues.append(f"Line {index}: unit price is negative.")

        if item.line_total is not None and item.line_total < 0:
            issues.append(f"Line {index}: line total is negative.")

        if (
            item.quantity is not None
            and item.unit_price is not None
            and item.line_total is not None
        ):
            calculated = item.quantity * item.unit_price

            if abs(calculated - item.line_total) > tolerance:
                issues.append(
                    f"Line {index}: quantity × unit price "
                    f"({calculated}) does not match line total "
                    f"({item.line_total})."
                )

        if item.line_total is not None:
            line_totals.append(item.line_total)

    if invoice.subtotal is not None and len(line_totals) == len(
        invoice.line_items
    ) and line_totals:
        calculated_subtotal = sum(line_totals, Decimal("0"))

        if abs(calculated_subtotal - invoice.subtotal) > tolerance:
            issues.append(
                f"Sum of line totals ({calculated_subtotal}) does not "
                f"match subtotal ({invoice.subtotal})."
            )

    if (
        invoice.subtotal is not None
        and invoice.tax_amount is not None
        and invoice.total_amount is not None
    ):
        calculated_total = invoice.subtotal + invoice.tax_amount

        if abs(calculated_total - invoice.total_amount) > tolerance:
            issues.append(
                f"Subtotal plus tax ({calculated_total}) does not "
                f"match invoice total ({invoice.total_amount})."
            )

    return issues


def finalize_extraction(
    data: ExtractedInvoice | dict[str, Any],
    original_text: str = "",
    translated_text: str = "",
) -> ExtractedInvoice:
    if isinstance(data, ExtractedInvoice):
        invoice = data
    else:
        invoice = ExtractedInvoice.model_validate(data)

    invoice.original_text = original_text or invoice.original_text
    invoice.translated_text = translated_text or invoice.translated_text

    required_values = {
        "vendor_name": invoice.vendor_name,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date,
        "po_number": invoice.po_number,
        "currency": invoice.currency,
        "line_items": invoice.line_items,
        "total_amount": invoice.total_amount,
    }

    missing = [
        field
        for field, value in required_values.items()
        if value is None or value == "" or value == []
    ]

    # Preserve model-supplied missing fields while removing duplicates.
    invoice.missing_fields = list(
        dict.fromkeys(invoice.missing_fields + missing)
    )

    if not invoice.invoice_number:
        invoice.review_reasons.append("Invoice number is missing.")

    if not invoice.po_number:
        invoice.review_reasons.append("Purchase order number is missing.")

    if not invoice.line_items:
        invoice.review_reasons.append("No invoice line items were extracted.")

    arithmetic_issues = check_invoice_consistency(invoice)
    invoice.review_reasons = list(
        dict.fromkeys(invoice.review_reasons + arithmetic_issues)
    )

    return invoice


# ---------------------------------------------------------------------
# Mapping into the existing workflow state
# ---------------------------------------------------------------------

def _line_items_for_state(
    invoice: ExtractedInvoice,
) -> list[dict[str, Any]]:
    """
    Map extracted line items to the dictionary structure used by
    business validation and persistence.
    """
    result: list[dict[str, Any]] = []

    for item in invoice.line_items:
        row = item.model_dump(mode="json")

        # Existing validation/persistence code accepts sku, sku_code,
        # or product_code. Preserve item_code as well.
        row["sku"] = normalize_sku(item.item_code)
        row["sku_code"] = row["sku"]
        row["product_code"] = row["sku"]

        result.append(row)

    return result

def _apply_corrections(
    extracted_values: dict[str, Any],
    corrections: dict[str, Any],
) -> dict[str, Any]:
    """
    Apply human corrections to effective values only.

    Original extracted values are never modified.

    Line-item corrections are merged into the matching original line,
    preserving fields that were not corrected.
    """

    aliases = {
        "extracted_invoice_number": "invoice_number",
        "extracted_vendor_name": "vendor_name",
        "extracted_po_number": "po_number",
        "extracted_invoice_date": "invoice_date",
        "extracted_currency": "currency",
        "extracted_subtotal_amount": "subtotal_amount",
        "extracted_tax_amount": "tax_amount",
        "extracted_tax_rate": "tax_rate",
        "extracted_total_amount": "total_amount",
        "extracted_line_items": "line_items",
    }

    # Shallow copy of the top-level dictionary.
    # Line items are copied separately below.
    effective = dict(extracted_values)

    corrections = corrections or {}

    for key, value in corrections.items():
        target = aliases.get(key, key)

        if value is None:
            continue

        # ============================================================
        # LINE ITEM CORRECTIONS
        # ============================================================
        if target == "line_items":

            original_lines = effective.get("line_items") or []

            # Copy every original line so the immutable extraction
            # remains untouched.
            merged_lines = [
                dict(line) if isinstance(line, dict) else line
                for line in original_lines
            ]

            if not isinstance(value, list):
                continue

            for correction in value:

                if not isinstance(correction, dict):
                    continue

                correction_sku = (
                    correction.get("item_code")
                    or correction.get("sku")
                    or correction.get("sku_code")
                    or correction.get("product_code")
                )

                correction_line_number = correction.get("line_number")

                matched_index = None

                # ----------------------------------------------------
                # Match by SKU first
                # ----------------------------------------------------
                if correction_sku:

                    normalized_correction_sku = normalize_sku(
                        correction_sku
                    )

                    for index, line in enumerate(merged_lines):

                        if not isinstance(line, dict):
                            continue

                        line_sku = (
                            line.get("item_code")
                            or line.get("sku")
                            or line.get("sku_code")
                            or line.get("product_code")
                        )

                        if (
                            line_sku
                            and normalize_sku(line_sku)
                            == normalized_correction_sku
                        ):
                            matched_index = index
                            break

                # ----------------------------------------------------
                # Fall back to line number
                # ----------------------------------------------------
                if (
                    matched_index is None
                    and correction_line_number is not None
                ):

                    for index, line in enumerate(merged_lines):

                        if not isinstance(line, dict):
                            continue

                        if (
                            line.get("line_number")
                            == correction_line_number
                            or index + 1 == correction_line_number
                        ):
                            matched_index = index
                            break

                # ----------------------------------------------------
                # If no matching line exists, add a new line
                # ----------------------------------------------------
                if matched_index is None:

                    new_line = dict(correction)

                    if correction_sku:

                        normalized_sku = normalize_sku(
                            correction_sku
                        )

                        new_line["item_code"] = normalized_sku
                        new_line["sku"] = normalized_sku
                        new_line["sku_code"] = normalized_sku
                        new_line["product_code"] = normalized_sku

                    merged_lines.append(new_line)
                    continue

                # ----------------------------------------------------
                # Merge only corrected fields
                # ----------------------------------------------------
                existing_line = merged_lines[matched_index]

                for field, corrected_value in correction.items():

                    if corrected_value is not None:
                        existing_line[field] = corrected_value

                # ----------------------------------------------------
                # Keep SKU aliases synchronized
                # ----------------------------------------------------
                corrected_sku = (
                    existing_line.get("item_code")
                    or existing_line.get("sku")
                    or existing_line.get("sku_code")
                    or existing_line.get("product_code")
                )

                if corrected_sku:

                    normalized_sku = normalize_sku(corrected_sku)

                    existing_line["item_code"] = normalized_sku
                    existing_line["sku"] = normalized_sku
                    existing_line["sku_code"] = normalized_sku
                    existing_line["product_code"] = normalized_sku

            # --------------------------------------------------------
            # Recalculate line totals AFTER all corrections
            # --------------------------------------------------------
            for line in merged_lines:

                if not isinstance(line, dict):
                    continue

                quantity = line.get("quantity")
                unit_price = line.get("unit_price")

                if quantity is None or unit_price is None:
                    continue

                try:
                    line["line_total"] = str(
                        Decimal(str(quantity))
                        * Decimal(str(unit_price))
                    )
                except (
                    InvalidOperation,
                    ValueError,
                    TypeError,
                ):
                    pass

            effective["line_items"] = merged_lines
            continue

        # ============================================================
        # SCALAR CORRECTIONS
        # ============================================================
        if target in effective:
            effective[target] = value

    return effective

# def _apply_corrections(
#     extracted_values: dict[str, Any],
#     corrections: dict[str, Any],
# ) -> dict[str, Any]:
#     """
#     Apply human corrections to effective values only. The immutable
#     extracted_* values are never modified here.
#     """
#     aliases = {
#         "extracted_invoice_number": "invoice_number",
#         "extracted_vendor_name": "vendor_name",
#         "extracted_po_number": "po_number",
#         "extracted_invoice_date": "invoice_date",
#         "extracted_currency": "currency",
#         "extracted_subtotal_amount": "subtotal_amount",
#         "extracted_tax_amount": "tax_amount",
#         "extracted_tax_rate": "tax_rate",
#         "extracted_total_amount": "total_amount",
#         "extracted_line_items": "line_items",
#     }

#     effective = dict(extracted_values)

#     for key, value in corrections.items():
#         target = aliases.get(key, key)

#         if target in effective and value is not None:
#             effective[target] = value

#     return effective


def extract_fields(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node: extract structured fields and map them into the
    existing InvoiceState naming conventions.

    The extracted_* fields remain the original model output. Effective
    values are separate and may incorporate previously submitted human
    corrections.
    """
    original_text = state.get("raw_extracted_text") or ""
    translated_text = (
        state.get("translated_text")
        or original_text
    )

    errors = list(state.get("errors") or [])
    warnings = list(state.get("warnings") or [])

    try:
        invoice = extract_invoice_fields(
            original_text=original_text,
            translated_text=translated_text,
        )

        line_items = _line_items_for_state(invoice)

        extracted_values: dict[str, Any] = {
            "invoice_number": invoice.invoice_number,
            "vendor_name": invoice.vendor_name,
            "po_number": invoice.po_number,
            "invoice_date": (
                invoice.invoice_date.isoformat()
                if invoice.invoice_date
                else None
            ),
            "currency": invoice.currency,
            "subtotal_amount": (
                str(invoice.subtotal)
                if invoice.subtotal is not None
                else None
            ),
            "tax_amount": (
                str(invoice.tax_amount)
                if invoice.tax_amount is not None
                else None
            ),
            "tax_rate": (
                str(invoice.tax_rate_percent)
                if invoice.tax_rate_percent is not None
                else None
            ),
            "total_amount": (
                str(invoice.total_amount)
                if invoice.total_amount is not None
                else None
            ),
            "line_items": line_items,
        }

        # Apply corrections only to the effective values.
        corrections = state.get("human_corrections") or {}
        effective = _apply_corrections(extracted_values, corrections)

        missing_fields = list(invoice.missing_fields)
        review_reasons = list(invoice.review_reasons)

        if missing_fields:
            warnings.append(
                "Extraction is missing fields: "
                + ", ".join(missing_fields)
            )

        if review_reasons:
            warnings.extend(review_reasons)

        result: dict[str, Any] = {
            # Original extraction: persisted as immutable extraction data.
            "extracted_invoice_number": extracted_values["invoice_number"],
            "extracted_vendor_name": extracted_values["vendor_name"],
            "extracted_po_number": extracted_values["po_number"],
            "extracted_invoice_date": extracted_values["invoice_date"],
            "extracted_currency": extracted_values["currency"],
            "extracted_subtotal_amount": extracted_values["subtotal_amount"],
            "extracted_tax_amount": extracted_values["tax_amount"],
            "extracted_tax_rate": extracted_values["tax_rate"],
            "extracted_total_amount": extracted_values["total_amount"],
            #"extracted_line_items": line_items,
            "extracted_line_items": extracted_values["line_items"],

            # Existing effective_* fields consumed by validation/persistence.
            "effective_invoice_number": effective["invoice_number"],
            "effective_vendor_name": effective["vendor_name"],
            "effective_po_number": effective["po_number"],
            "effective_invoice_date": effective["invoice_date"],
            "effective_currency": effective["currency"],
            "effective_subtotal_amount": effective["subtotal_amount"],
            "effective_tax_amount": effective["tax_amount"],
            "effective_tax_rate": effective["tax_rate"],
            "effective_total_amount": effective["total_amount"],
            "effective_line_items": effective["line_items"],

            # Canonical fields already declared in InvoiceState.
            "invoice_number": effective["invoice_number"],
            "vendor_name": effective["vendor_name"],
            "po_number": effective["po_number"],
            "invoice_date": effective["invoice_date"],
            "currency": effective["currency"],
            "subtotal_amount": effective["subtotal_amount"],
            "tax_amount": effective["tax_amount"],
            "tax_rate": effective["tax_rate"],
            "total_amount": effective["total_amount"],
            "line_items": effective["line_items"],

            "document_type": invoice.document_type,
            "missing_fields": missing_fields,
            "field_extraction_review_reasons": review_reasons,
            "field_extraction_passed": not missing_fields,
            "human_review_required": bool(
                state.get("human_review_required")
                or missing_fields
                or review_reasons
            ),
            "warnings": list(dict.fromkeys(warnings)),
            "processing_status": "field_extraction_complete",
        }

        # Preserve existing errors instead of replacing the whole list.
        if errors:
            result["errors"] = errors

        return result

    except Exception as exc:
        errors.append(f"Field extraction failed: {exc}")

        return {
            "field_extraction_passed": False,
            "human_review_required": True,
            "errors": errors,
            "processing_status": "failed",
        }
