from __future__ import annotations

from typing import Any

import streamlit as st


def render_feedback_form(
    invoice: dict[str, Any],
) -> dict[str, Any] | None:

    invoice_id = invoice.get(
        "invoice_id"
    )

    status = invoice.get(
        "validation_status"
    )

    human_review = invoice.get(
        "human_review_required"
    )

    if not human_review and status != "manual_review":
        return None

    st.divider()

    st.subheader("Human Review")

    st.warning(
        "This invoice requires manual review. "
        "Corrections are stored as human feedback "
        "and the original extraction is preserved."
    )

    line_items = invoice.get(
        "line_items",
        [],
    )

    corrections: dict[str, Any] = {}

    if line_items:

        st.markdown(
            "### Correct extracted values"
        )

        for index, line in enumerate(
            line_items
        ):

            line_number = line.get(
                "line_number",
                index + 1,
            )

            sku = line.get(
                "sku",
                "",
            )

            st.markdown(
                f"**Line {line_number} — "
                f"{sku or 'Unknown SKU'}**"
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                quantity = st.number_input(
                    "Quantity",
                    value=float(
                        line.get(
                            "quantity"
                        ) or 0
                    ),
                    min_value=0.0,
                    key=(
                        f"qty_"
                        f"{invoice_id}_"
                        f"{line_number}"
                    ),
                )

            with col2:
                unit_price = st.number_input(
                    "Unit Price",
                    value=float(
                        line.get(
                            "unit_price"
                        ) or 0
                    ),
                    min_value=0.0,
                    key=(
                        f"price_"
                        f"{invoice_id}_"
                        f"{line_number}"
                    ),
                )

            with col3:
                line_total = st.number_input(
                    "Line Total",
                    value=float(
                        line.get(
                            "line_total"
                        ) or 0
                    ),
                    min_value=0.0,
                    key=(
                        f"total_"
                        f"{invoice_id}_"
                        f"{line_number}"
                    ),
                )

            corrections[
                f"line_{line_number}"
            ] = {
                "sku": sku,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            }

    st.markdown(
        "### Review decision"
    )

    decision = st.radio(
        "Decision",
        [
            "manual_review",
            "approve",
            "reject",
        ],
        horizontal=True,
        key=f"decision_{invoice_id}",
    )

    feedback = st.text_area(
        "Reviewer comments",
        placeholder=(
            "Explain the correction or "
            "review decision..."
        ),
        key=f"feedback_{invoice_id}",
    )

    if st.button(
        "Submit Human Review",
        type="primary",
        key=f"submit_hitl_{invoice_id}",
    ):
        return {
            "corrections": corrections,
            "decision": decision,
            "feedback": feedback.strip(),
        }

    return None