from __future__ import annotations

from typing import Any

import requests

from agent.config import settings


class ERPClientError(Exception):
    """Raised when the Mock ERP service cannot be reached or returns an error."""

    pass


class ERPClient:
    """
    HTTP client for the Mock ERP service.

    The Agent must communicate with ERP data only through this client.
    It must never query the PostgreSQL `erp` schema directly.
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

        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    # ============================================================
    # INTERNAL REQUEST
    # ============================================================

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
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
                "Mock ERP returned an invalid JSON response."
            ) from exc

        if not isinstance(data, dict):
            raise ERPClientError(
                "Mock ERP response must be a JSON object."
            )

        return data

    # ============================================================
    # HEALTH
    # ============================================================

    def health_check(self) -> bool:
        try:
            data = self._request(
                "GET",
                "/health",
            )

            return data.get("status") in {
                "ok",
                "healthy",
            }

        except ERPClientError:
            return False

    # ============================================================
    # VENDOR
    # ============================================================

    def find_vendor(
        self,
        vendor_name: str,
    ) -> dict[str, Any] | None:
        """
        Find a vendor through Mock ERP.

        Expected endpoint:

            GET /vendor/search?name=<vendor_name>
        """

        if not vendor_name:
            return None

        data = self._request(
            "GET",
            "/vendor/search",
            params={
                "name": vendor_name,
            },
        )

        vendor = data.get("vendor")

        if vendor is None:
            return None

        if not isinstance(vendor, dict):
            raise ERPClientError(
                "Invalid vendor response from Mock ERP."
            )

        return vendor

    # ============================================================
    # PURCHASE ORDER
    # ============================================================

    def get_purchase_order(
        self,
        po_number: str,
    ) -> dict[str, Any] | None:
        """
        Retrieve a purchase order through Mock ERP.

        Expected endpoint:

            GET /purchase-order/{po_number}

        Expected normalized response:

            {
                "po_number": "...",
                "vendor_id": "...",
                "currency": "...",
                "line_items": [...]
            }
        """

        if not po_number:
            return None

        data = self._request(
            "GET",
            f"/purchase-order/{po_number}",
        )

        if not data:
            return None

        # Support the normalized API contract.
        if "purchase_order" in data:

            purchase_order = data.get(
                "purchase_order"
            )

            line_items = data.get(
                "line_items",
                [],
            )

            if not isinstance(purchase_order, dict):
                raise ERPClientError(
                    "Invalid purchase_order object from Mock ERP."
                )

            normalized = dict(purchase_order)

            if "line_items" not in normalized:
                normalized["line_items"] = line_items

            return normalized

        # Also accept an already-normalized response.
        return data

    # ============================================================
    # SKU
    # ============================================================

    def get_sku(
        self,
        sku_code: str,
    ) -> dict[str, Any] | None:
        """
        Retrieve SKU information through Mock ERP.

        Expected endpoint:

            GET /sku/{sku_code}
        """

        if not sku_code:
            return None

        data = self._request(
            "GET",
            f"/sku/{sku_code}",
        )

        if not data:
            return None

        sku = data.get("sku", data)

        if not isinstance(sku, dict):
            raise ERPClientError(
                "Invalid SKU response from Mock ERP."
            )

        return sku

    # ============================================================
    # MULTIPLE SKUS
    # ============================================================

    def get_skus(
        self,
        sku_codes: list[str],
    ) -> list[dict[str, Any]]:
        """
        Retrieve multiple SKU records.

        Uses the individual SKU endpoint so this client remains
        compatible with the simple Mock ERP API.
        """

        results: list[dict[str, Any]] = []

        for sku_code in sku_codes:

            sku = self.get_sku(sku_code)

            if sku is not None:
                results.append(sku)

        return results

    # ============================================================
    # CLOSE
    # ============================================================

    def close(self) -> None:
        self.session.close()


# ================================================================
# GLOBAL ERP CLIENT
# ================================================================

erp_client = ERPClient()