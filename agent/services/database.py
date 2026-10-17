from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Iterable

from psycopg2 import DatabaseError
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from agent.config import settings


class DatabaseErrorHandler(Exception):
    """
    Application-level database exception.

    Database-specific exceptions are converted into this exception
    so the rest of the application does not need to depend on the
    PostgreSQL driver implementation.
    """

    pass


class Database:
    """
    PostgreSQL connection manager.

    Responsibilities:
        - Manage PostgreSQL connections
        - Execute SQL
        - Fetch rows
        - Handle transactions
        - Provide health checks

    This class does NOT contain business logic.

    Important architecture rule:
        Agent application code must not directly query ERP tables.
        ERP access must go through mock-erp.

    Therefore this class is primarily used for:
        - audit schema
        - langgraph schema
        - application persistence
    """

    def __init__(self) -> None:
        self._pool: pool.ThreadedConnectionPool | None = None

    # ============================================================
    # CONNECTION CONFIGURATION
    # ============================================================

    @property
    def connection_kwargs(self) -> dict[str, Any]:
        """
        PostgreSQL connection configuration.

        Docker service names come from agent.config.Settings.
        """

        return {
            "host": settings.postgres_host,
            "port": settings.postgres_port,
            "dbname": settings.postgres_db,
            "user": settings.postgres_user,
            "password": settings.postgres_password,
        }

    # ============================================================
    # CONNECTION POOL
    # ============================================================

    def initialize(self) -> None:
        """
        Initialize the PostgreSQL connection pool.

        The pool is created lazily because importing the application
        should not immediately require PostgreSQL to be available.
        """

        if self._pool is not None:
            return

        try:
            self._pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                **self.connection_kwargs,
            )

        except DatabaseError as exc:
            self._pool = None

            raise DatabaseErrorHandler(
                f"Unable to initialize PostgreSQL connection pool: {exc}"
            ) from exc

    def close(self) -> None:
        """
        Close all connections in the pool.
        """

        if self._pool is not None:
            self._pool.closeall()
            self._pool = None

    # ============================================================
    # CONNECTION ACQUISITION
    # ============================================================

    def _get_pool(self) -> pool.ThreadedConnectionPool:
        """
        Return an initialized connection pool.
        """

        if self._pool is None:
            self.initialize()

        if self._pool is None:
            raise DatabaseErrorHandler(
                "PostgreSQL connection pool is not available."
            )

        return self._pool

    @contextmanager
    def connection(self) -> Generator[Any, None, None]:
        """
        Borrow a connection from the pool.

        The connection is always returned to the pool.
        """

        connection_pool = self._get_pool()
        connection = None

        try:
            connection = connection_pool.getconn()

            if connection is None:
                raise DatabaseErrorHandler(
                    "PostgreSQL connection pool returned no connection."
                )

            yield connection

        except DatabaseError as exc:
            raise DatabaseErrorHandler(
                f"PostgreSQL connection error: {exc}"
            ) from exc

        finally:
            if connection is not None:
                connection_pool.putconn(connection)

    # ============================================================
    # TRANSACTION
    # ============================================================

    @contextmanager
    def transaction(self) -> Generator[Any, None, None]:
        """
        Execute multiple database operations as one transaction.

        Example:

            with db.transaction() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(...)
                    cursor.execute(...)

        If an exception occurs, the transaction is rolled back.

        Otherwise it is committed.
        """

        connection_pool = self._get_pool()
        connection = None

        try:
            connection = connection_pool.getconn()

            if connection is None:
                raise DatabaseErrorHandler(
                    "Unable to obtain PostgreSQL connection."
                )

            yield connection

            connection.commit()

        except DatabaseError as exc:

            if connection is not None:
                connection.rollback()

            raise DatabaseErrorHandler(
                f"PostgreSQL transaction failed: {exc}"
            ) from exc

        except Exception:

            if connection is not None:
                connection.rollback()

            raise

        finally:

            if connection is not None:
                connection_pool.putconn(connection)

    # ============================================================
    # EXECUTE
    # ============================================================

    def execute(
        self,
        query: str,
        params: Iterable[Any] | None = None,
    ) -> int:
        """
        Execute an INSERT, UPDATE, DELETE or DDL statement.

        Returns:
            Number of affected rows.
        """

        try:

            with self.transaction() as connection:

                with connection.cursor() as cursor:

                    cursor.execute(
                        query,
                        tuple(params) if params is not None else None,
                    )

                    return cursor.rowcount

        except DatabaseErrorHandler:
            raise

        except Exception as exc:
            raise DatabaseErrorHandler(
                f"Database execution failed: {exc}"
            ) from exc

    # ============================================================
    # FETCH ONE
    # ============================================================

    def fetch_one(
        self,
        query: str,
        params: Iterable[Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Execute a SELECT query and return one row.

        Rows are returned as dictionaries.
        """

        try:

            with self.connection() as connection:

                with connection.cursor(
                    cursor_factory=RealDictCursor
                ) as cursor:

                    cursor.execute(
                        query,
                        tuple(params) if params is not None else None,
                    )

                    row = cursor.fetchone()

                    if row is None:
                        return None

                    return dict(row)

        except DatabaseErrorHandler:
            raise

        except Exception as exc:
            raise DatabaseErrorHandler(
                f"Database fetch_one failed: {exc}"
            ) from exc

    # ============================================================
    # FETCH ALL
    # ============================================================

    def fetch_all(
        self,
        query: str,
        params: Iterable[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a SELECT query and return all rows.

        Rows are returned as dictionaries.
        """

        try:

            with self.connection() as connection:

                with connection.cursor(
                    cursor_factory=RealDictCursor
                ) as cursor:

                    cursor.execute(
                        query,
                        tuple(params) if params is not None else None,
                    )

                    rows = cursor.fetchall()

                    return [dict(row) for row in rows]

        except DatabaseErrorHandler:
            raise

        except Exception as exc:
            raise DatabaseErrorHandler(
                f"Database fetch_all failed: {exc}"
            ) from exc

    # ============================================================
    # INSERT AND RETURNING
    # ============================================================

    def insert_returning(
        self,
        query: str,
        params: Iterable[Any] | None = None,
    ) -> Any | None:
        """
        Execute INSERT ... RETURNING and return the first returned value.
        """

        try:
            with self.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        query,
                        tuple(params) if params is not None else None,
                    )

                    row = cursor.fetchone()

                    if row is None:
                        return None

                    # PostgreSQL RETURNING should always provide at least
                    # one column. Fail with useful diagnostics otherwise.
                    if len(row) < 1:
                        raise DatabaseErrorHandler(
                            f"INSERT ... RETURNING returned an empty row. "
                            f"Query={query[:300]}"
                        )

                    return row[0]

        except DatabaseErrorHandler:
            raise

        except Exception as exc:
            raise DatabaseErrorHandler(
                f"Database insert_returning failed: {exc}"
            ) from exc
    # ============================================================
    # HEALTH CHECK
    # ============================================================

    def health_check(self) -> bool:
        """
        Check whether PostgreSQL is reachable.
        """

        try:

            row = self.fetch_one(
                "SELECT 1 AS healthy"
            )

            return bool(
                row
                and row.get("healthy") == 1
            )

        except DatabaseErrorHandler:
            return False

    # ============================================================
    # TRANSACTIONAL MULTI-STATEMENT EXECUTION
    # ============================================================

    def execute_many(
        self,
        query: str,
        parameter_sets: Iterable[Iterable[Any]],
    ) -> int:
        """
        Execute the same statement for multiple parameter sets
        inside a single transaction.

        Useful for:
            - invoice line items
            - discrepancy records
            - RAG metadata
            - human feedback records
        """

        try:

            with self.transaction() as connection:

                with connection.cursor() as cursor:

                    cursor.executemany(
                        query,
                        [
                            tuple(params)
                            for params in parameter_sets
                        ],
                    )

                    return cursor.rowcount

        except DatabaseErrorHandler:
            raise

        except Exception as exc:
            raise DatabaseErrorHandler(
                f"Database execute_many failed: {exc}"
            ) from exc


# ================================================================
# GLOBAL DATABASE INSTANCE
# ================================================================

db = Database()