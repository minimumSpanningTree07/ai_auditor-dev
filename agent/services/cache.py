from __future__ import annotations

import json
from typing import Any

import redis

from agent.config import settings


class CacheError(Exception):
    """Raised when a cache operation fails."""

    pass


class Cache:
    def __init__(self) -> None:
        self._client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )

    def _serialize(self, value: Any) -> str:
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError) as exc:
            raise CacheError(
                f"Unable to serialize cache value: {exc}"
            ) from exc

    def _deserialize(self, value: str | None) -> Any:
        if value is None:
            return None

        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise CacheError(
                f"Unable to deserialize cache value: {exc}"
            ) from exc

    def get(self, key: str) -> Any:
        try:
            return self._deserialize(
                self._client.get(key)
            )
        except redis.RedisError as exc:
            raise CacheError(
                f"Redis get failed: {exc}"
            ) from exc

    def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        try:
            return bool(
                self._client.set(
                    key,
                    self._serialize(value),
                    ex=ttl or settings.redis_ttl,
                )
            )
        except redis.RedisError as exc:
            raise CacheError(
                f"Redis set failed: {exc}"
            ) from exc

    def delete(self, key: str) -> bool:
        try:
            return bool(
                self._client.delete(key)
            )
        except redis.RedisError as exc:
            raise CacheError(
                f"Redis delete failed: {exc}"
            ) from exc

    def exists(self, key: str) -> bool:
        try:
            return bool(
                self._client.exists(key)
            )
        except redis.RedisError as exc:
            raise CacheError(
                f"Redis exists failed: {exc}"
            ) from exc

    def clear_prefix(self, prefix: str) -> int:
        try:
            keys = list(
                self._client.scan_iter(
                    match=f"{prefix}*"
                )
            )

            if not keys:
                return 0

            return int(
                self._client.delete(*keys)
            )

        except redis.RedisError as exc:
            raise CacheError(
                f"Redis prefix deletion failed: {exc}"
            ) from exc

    def health_check(self) -> bool:
        try:
            return bool(
                self._client.ping()
            )
        except redis.RedisError:
            return False

    def close(self) -> None:
        try:
            self._client.close()
        except redis.RedisError:
            pass


cache = Cache()