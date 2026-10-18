from __future__ import annotations

import os
from typing import Any

import requests


AGENT_URL = os.getenv(
    "AGENT_URL",
    "http://localhost:8000",
).rstrip("/")


class AgentAPIError(Exception):
    pass


def _request(
    method: str,
    path: str,
    **kwargs: Any,
) -> Any:

    url = f"{AGENT_URL}{path}"

    try:
        response = requests.request(
            method,
            url,
            timeout=120,
            **kwargs,
        )
    except requests.RequestException as exc:
        raise AgentAPIError(
            f"Unable to connect to Agent API: {exc}"
        ) from exc

    if not response.ok:
        try:
            detail = response.json()
        except Exception:
            detail = response.text

        raise AgentAPIError(
            f"Agent API returned {response.status_code}: {detail}"
        )

    if not response.content:
        return {}

    try:
        return response.json()
    except Exception:
        return response.text


def health() -> dict[str, Any]:
    return _request(
        "GET",
        "/health",
    )


def get_dashboard_summary() -> dict[str, Any]:
    return _request(
        "GET",
        "/api/dashboard/summary",
    )


def get_invoices() -> list[dict[str, Any]]:
    return _request(
        "GET",
        "/api/invoices",
    )


def get_invoice(
    invoice_id: str,
) -> dict[str, Any]:

    return _request(
        "GET",
        f"/api/invoices/{invoice_id}",
    )


def get_report(
    invoice_id: str,
) -> dict[str, Any]:

    return _request(
        "GET",
        f"/api/invoices/{invoice_id}/report",
    )


def upload_invoice(
    filename: str,
    content: bytes,
) -> dict[str, Any]:

    return _request(
        "POST",
        "/api/invoices/upload",
        files={
            "file": (
                filename,
                content,
                "application/octet-stream",
            )
        },
    )


def revalidate_invoice(
    invoice_id: str,
    corrections: dict[str, Any] | None = None,
    decision: str | None = None,
    feedback: str | None = None,
) -> dict[str, Any]:

    return _request(
        "POST",
        f"/api/invoices/{invoice_id}/revalidate",
        json={
            "corrections": corrections or {},
            "decision": decision,
            "feedback": feedback,
        },
    )


def ask_ai(
    question: str,
    invoice_id: str | None = None,
) -> dict[str, Any]:

    payload = {
        "question": question,
        "invoice_id": invoice_id,
    }

    return _request(
        "POST",
        "/api/query",
        json=payload,
    )