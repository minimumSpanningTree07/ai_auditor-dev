from __future__ import annotations

import os
from typing import Any

import requests


AGENT_URL = os.getenv(
    "AGENT_URL",
    "http://agent:8000",
)


class APIClient:
    def __init__(
        self,
        base_url: str = AGENT_URL,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        response = requests.request(
            method,
            f"{self.base_url}{path}",
            timeout=self.timeout,
            **kwargs,
        )

        response.raise_for_status()
        return response.json()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def dashboard_summary(self) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/dashboard/summary",
        )

    def get_invoices(self) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/api/invoices",
        )

    def get_invoice(
        self,
        invoice_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/invoices/{invoice_id}",
        )

    def upload_invoice(
        self,
        file,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/invoices/upload",
            files={
                "file": (
                    file.name,
                    file,
                    getattr(
                        file,
                        "type",
                        "application/octet-stream",
                    ),
                )
            },
        )

    def revalidate_invoice(
        self,
        invoice_id: str,
        corrections: dict[str, Any] | None = None,
        decision: str | None = None,
        feedback: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/invoices/{invoice_id}/revalidate",
            json={
                "corrections": corrections or {},
                "decision": decision,
                "feedback": feedback,
            },
        )

    def get_report(
        self,
        invoice_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/invoices/{invoice_id}/report",
        )


api_client = APIClient()