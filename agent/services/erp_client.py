
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests

from agent.config import settings


class ERPClientError(Exception):
    """Raised when the Mock ERP service cannot be reached or returns an error."""


class ERPClient:
    """
    HTTP client for Mock ERP.

    ERP data must be accessed through this HTTP API.
    The agent must not query ERP tables in PostgreSQL directly.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = 10,
    ) -> None:
        self.base_url = (
            base_url
            or f"http://{settings.mock_erp_host}:{settings.mock_erp_port}"
        ).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ERPClientError(
                f"Unable to connect to Mock ERP: {exc}"
            ) from exc

        if response.status_code == 404:
            return {}

        if not response.ok:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text

            raise ERPClientError(
                f"Mock ERP returned HTTP {response.status_code}: {detail}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ERPClientError(
                "Mock ERP returned invalid JSON."
            ) from exc

        if not isinstance(data, dict):
            raise ERPClientError(
                "Mock ERP response must be a JSON object."
            )

        return data

    @staticmethod
    def _unwrap(
        data: dict[str, Any],
        key: str,
    ) -> dict[str, Any]:
        """Accept either a direct object or a wrapped object."""
        value = data.get(key, data)

        if not isinstance(value, dict):
            raise ERPClientError(
                f"Invalid {key} response from Mock ERP."
            )

        return value

    def health_check(self) -> bool:
        try:
            data = self._request("GET", "/health")
            status = data.get("status")

            # Your mock ERP currently returns a boolean here.
            if status is True:
                return True

            return status in {"ok", "healthy"}

        except ERPClientError:
            return False

    def find_vendor(
        self,
        vendor_name: str,
    ) -> dict[str, Any] | None:
        """
        Compatibility method for callers that only know a vendor name.

        This uses the existing name-search route. The required
        vendor-by-ID route is implemented in get_vendor().
        """
        if not vendor_name:
            return None

        data = self._request(
            "GET",
            "/vendor/search",
            params={"name": vendor_name},
        )

        if not data:
            return None

        return self._unwrap(data, "vendor")

    def get_vendor(
        self,
        vendor_id: str,
    ) -> dict[str, Any] | None:
        """GET /vendor/{vendor_id}."""
        if not vendor_id:
            return None

        data = self._request(
            "GET",
            f"/vendor/{quote(vendor_id, safe='')}",
        )

        if not data:
            return None

        return self._unwrap(data, "vendor")

    def get_purchase_order(
        self,
        po_number: str,
    ) -> dict[str, Any] | None:
        """GET /po/{po_number}; returns the PO header and line items."""
        if not po_number:
            return None

        data = self._request(
            "GET",
            f"/po/{quote(po_number, safe='')}",
        )

        if not data:
            return None

        # Support either a direct PO object or a wrapped response.
        if "purchase_order" in data:
            purchase_order = data["purchase_order"]

            if not isinstance(purchase_order, dict):
                raise ERPClientError(
                    "Invalid purchase_order object from Mock ERP."
                )

            normalized = dict(purchase_order)
            if "line_items" not in normalized:
                normalized["line_items"] = data.get("line_items", [])
            return normalized

        return data

    def get_sku(
        self,
        sku_code: str,
    ) -> dict[str, Any] | None:
        """GET /sku/{sku_code}."""
        if not sku_code:
            return None

        data = self._request(
            "GET",
            f"/sku/{quote(sku_code, safe='')}",
        )

        if not data:
            return None

        return self._unwrap(data, "sku")

    def get_skus(
        self,
        sku_codes: list[str],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        for sku_code in sku_codes:
            sku = self.get_sku(sku_code)
            if sku is not None:
                results.append(sku)

        return results

    def close(self) -> None:
        self.session.close()


erp_client = ERPClient()
