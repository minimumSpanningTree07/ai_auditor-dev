from __future__ import annotations

import os
from typing import Any

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor


class ERPRepository:

    def __init__(self) -> None:
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "invoice_auditor"),
            user=os.getenv("POSTGRES_USER", "invoice_user"),
            password=os.getenv("POSTGRES_PASSWORD", "invoice_password"),
        )

    def initialize(self) -> None:
        conn = self.pool.getconn()

        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            self.pool.putconn(conn)

    def health_check(self) -> bool:
        try:
            conn = self.pool.getconn()

            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                return True
            finally:
                self.pool.putconn(conn)

        except Exception:
            return False

    def close(self) -> None:
        if self.pool:
            self.pool.closeall()

    def _fetch_one(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> dict[str, Any] | None:

        conn = self.pool.getconn()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                row = cur.fetchone()

                return dict(row) if row else None

        finally:
            self.pool.putconn(conn)

    def _fetch_all(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:

        conn = self.pool.getconn()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)

                return [dict(row) for row in cur.fetchall()]

        finally:
            self.pool.putconn(conn)

    # ---------------------------------------------------------
    # VENDORS
    # ---------------------------------------------------------

    def get_vendor(
        self,
        vendor_id: str,
    ) -> dict[str, Any] | None:

        return self._fetch_one(
            """
            SELECT
                vendor_id,
                vendor_name,
                currency,
                country
            FROM erp.vendors
            WHERE vendor_id = %s
            LIMIT 1
            """,
            (vendor_id,),
        )

    def find_vendor(
        self,
        name: str,
    ) -> dict[str, Any] | None:

        if not name:
            return None

        return self._fetch_one(
            """
            SELECT
                vendor_id,
                vendor_name,
                currency,
                country
            FROM erp.vendors
            WHERE LOWER(TRIM(vendor_name)) =
                  LOWER(TRIM(%s))
            LIMIT 1
            """,
            (name,),
        )

    def list_vendors(self) -> list[dict[str, Any]]:

        return self._fetch_all(
            """
            SELECT
                vendor_id,
                vendor_name,
                currency,
                country
            FROM erp.vendors
            ORDER BY vendor_id
            """
        )

    # ---------------------------------------------------------
    # PURCHASE ORDERS
    # ---------------------------------------------------------

    # def get_purchase_order(
    #     self,
    #     po_number: str,
    # ) -> dict[str, Any] | None:

    #     if not po_number:
    #         return None

    #     purchase_order = self._fetch_one(
    #         """
    #         SELECT
    #             po_number,
    #             vendor_id,
    #             vendor_name,
    #             currency,
    #             status
    #         FROM erp.purchase_orders
    #         WHERE po_number = %s
    #         LIMIT 1
    #         """,
    #         (po_number,),
    #     )

    #     if purchase_order is None:
    #         return None

    #     lines = self._fetch_all(
    #         """
    #         SELECT
    #             sku,
    #             description,
    #             quantity,
    #             unit_price,
    #             currency
    #         FROM erp.purchase_order_lines
    #         WHERE po_number = %s
    #         ORDER BY id
    #         """,
    #         (po_number,),
    #     )

    #     purchase_order["lines"] = lines

    #     return purchase_order

    # def list_purchase_orders(self) -> list[dict[str, Any]]:

    #     return self._fetch_all(
    #         """
    #         SELECT
    #             po_number,
    #             vendor_id,
    #             vendor_name,
    #             currency,
    #             status
    #         FROM erp.purchase_orders
    #         ORDER BY po_number
    #         """
    #     )


    def find_vendor_by_name(self, name: str) -> dict[str, Any] | None:
        if not name:
            return None

        return self._fetch_one(
            """
            SELECT
                vendor_id,
                vendor_code,
                vendor_name,
                currency,
                country,
                active
            FROM erp.vendors
            WHERE LOWER(TRIM(vendor_name)) = LOWER(TRIM(%s))
            LIMIT 1
            """,
            (name,),
        )
    def get_purchase_order(
        self,
        po_number: str,
    ) -> dict[str, Any] | None:

        if not po_number:
            return None

        purchase_order = self._fetch_one(
            """
            SELECT
                po_number,
                vendor_id,
                vendor_name,
                order_date,
                currency,
                status
            FROM erp.purchase_orders
            WHERE po_number = %s
            LIMIT 1
            """,
            (po_number.strip(),),
        )

        if purchase_order is None:
            return None

        line_items = self._fetch_all(
            """
            SELECT
                line_number,
                sku,
                description,
                quantity,
                unit_price,
                currency
            FROM erp.purchase_order_lines
            WHERE po_number = %s
            ORDER BY line_number
            """,
            (po_number.strip(),),
        )

        purchase_order["line_items"] = line_items

        return purchase_order

    # ---------------------------------------------------------
    # SKU
    # ---------------------------------------------------------
    def get_sku(self, sku_code: str) -> dict[str, Any] | None:
        if not sku_code:
            return None

        return self._fetch_one(
            """
            SELECT
                sku,
                description,
                unit_of_measure,
                active
            FROM erp.skus
            WHERE LOWER(TRIM(sku)) = LOWER(TRIM(%s))
            LIMIT 1
            """,
            (sku_code,),
        )
    # def get_sku(
    #     self,
    #     sku_code: str,
    # ) -> dict[str, Any] | None:

    #     if not sku_code:
    #         return None

    #     return self._fetch_one(
    #         """
    #         SELECT
    #             sku,
    #             description,
    #             unit_of_measure
    #         FROM erp.skus
    #         WHERE sku = %s
    #         LIMIT 1
    #         """,
    #         (sku_code,),
    #     )

    def list_skus(self) -> list[dict[str, Any]]:

        return self._fetch_all(
            """
            SELECT
                sku,
                description,
                unit_of_measure
            FROM erp.skus
            ORDER BY sku
            """
        )


repository = ERPRepository()