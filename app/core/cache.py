import json
import logging
from collections.abc import Awaitable
from datetime import date, datetime
from typing import Any, cast

from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


class CacheService:
    def __init__(self, client: Redis) -> None:
        self.client = client

    async def get_json(self, key: str) -> dict[str, Any] | list[Any] | None:
        try:
            value = await self.client.get(key)
        except Exception:  # pragma: no cover - defensive for infrastructure issues
            logger.exception("Redis get failed", extra={"cache_key": key})
            return None
        if value is None:
            return None
        return json.loads(value)

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            await self.client.set(key, json.dumps(value, default=_json_default), ex=ttl_seconds)
        except Exception:  # pragma: no cover - defensive for infrastructure issues
            logger.exception("Redis set failed", extra={"cache_key": key})

    async def delete(self, key: str) -> None:
        try:
            await self.client.delete(key)
        except Exception:  # pragma: no cover - defensive for infrastructure issues
            logger.exception("Redis delete failed", extra={"cache_key": key})

    async def delete_prefix(self, prefix: str) -> None:
        try:
            cursor = 0
            pattern = f"{prefix}*"
            while True:
                cursor, keys = await self.client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    await self.client.delete(*keys)
                if cursor == 0:
                    break
        except Exception:  # pragma: no cover - defensive for infrastructure issues
            logger.exception("Redis prefix delete failed", extra={"cache_prefix": prefix})

    async def ping(self) -> bool:
        try:
            pong = cast(Awaitable[bool], self.client.ping())
            return await pong
        except Exception:
            return False


def get_cache_service() -> CacheService:
    return CacheService(redis_client)
