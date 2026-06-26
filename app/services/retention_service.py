from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.core.cache import CacheService, get_cache_service
from app.utils.time_utils import singapore_now

logger = logging.getLogger(__name__)

RETENTION_DAYS = (1, 2, 3, 4, 5, 6, 7, 15, 30)
FIRST_SEEN_TTL_SECONDS = 180 * 24 * 60 * 60
DAILY_SET_TTL_SECONDS = 60 * 24 * 60 * 60
RETENTION_KEY_PREFIX = "retention"
RETENTION_PLATFORMS = ("all", "ios", "android", "unknown")
TRACKED_PLATFORMS = ("ios", "android")


@dataclass(frozen=True)
class RetentionMetric:
    day: int
    date: str
    retained_users: int | None
    rate: float | None


class RetentionService:
    def __init__(self, cache: CacheService) -> None:
        self.cache = cache

    async def track_activity(
        self,
        device_id: str | None,
        path: str,
        status_code: int | None,
        *,
        device_platform: str | None = None,
        activity_date: date | None = None,
    ) -> None:
        if not should_track_activity(device_id, path, status_code):
            return

        normalized_device_id = device_id.strip()
        normalized_platform = normalize_retention_platform(device_platform, default="unknown")
        current_date = activity_date or singapore_now().date()
        date_text = current_date.isoformat()

        try:
            pipeline = self.cache.client.pipeline(transaction=False)
            first_seen_key = _first_seen_key(normalized_device_id)
            active_key = _active_key(date_text)
            pipeline.set(
                first_seen_key,
                date_text,
                ex=FIRST_SEEN_TTL_SECONDS,
                nx=True,
            )
            pipeline.sadd(active_key, normalized_device_id)
            pipeline.expire(active_key, DAILY_SET_TTL_SECONDS)
            platform_first_seen_key = _first_seen_key(normalized_device_id, normalized_platform)
            platform_active_key = _active_key(date_text, normalized_platform)
            pipeline.set(
                platform_first_seen_key,
                date_text,
                ex=FIRST_SEEN_TTL_SECONDS,
                nx=True,
            )
            pipeline.sadd(platform_active_key, normalized_device_id)
            pipeline.expire(platform_active_key, DAILY_SET_TTL_SECONDS)
            result = await pipeline.execute()

            is_new_user = bool(result[0])
            is_new_platform_user = bool(result[3])
            if not is_new_user and not is_new_platform_user:
                return

            cohort_pipeline = self.cache.client.pipeline(transaction=False)
            if is_new_user:
                cohort_key = _cohort_key(date_text)
                cohort_pipeline.sadd(cohort_key, normalized_device_id)
                cohort_pipeline.expire(cohort_key, DAILY_SET_TTL_SECONDS)
            if is_new_platform_user:
                platform_cohort_key = _cohort_key(date_text, normalized_platform)
                cohort_pipeline.sadd(platform_cohort_key, normalized_device_id)
                cohort_pipeline.expire(platform_cohort_key, DAILY_SET_TTL_SECONDS)
            await cohort_pipeline.execute()
        except Exception:  # pragma: no cover - defensive for infrastructure issues
            logger.exception("Retention tracking failed")

    async def get_retention_range(
        self,
        start_date: date,
        end_date: date,
        *,
        platform: str = "all",
        today: date | None = None,
    ) -> dict[str, Any]:
        if end_date < start_date:
            start_date, end_date = end_date, start_date

        normalized_platform = normalize_retention_platform(platform, default="all")
        current_date = today or singapore_now().date()
        rows = []
        cursor = start_date
        while cursor <= end_date:
            rows.append(
                await self.get_retention(
                    cursor,
                    platform=normalized_platform,
                    today=current_date,
                )
            )
            cursor += timedelta(days=1)

        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timezone": "Asia/Singapore",
            "platform": normalized_platform,
            "platforms": list(RETENTION_PLATFORMS),
            "retention_days": list(RETENTION_DAYS),
            "rows": rows,
        }

    async def get_retention(
        self,
        cohort_date: date,
        *,
        platform: str = "all",
        today: date | None = None,
    ) -> dict[str, Any]:
        normalized_platform = normalize_retention_platform(platform, default="all")
        current_date = today or singapore_now().date()
        cohort_date_text = cohort_date.isoformat()
        cohort_key = _cohort_key(cohort_date_text, normalized_platform)

        try:
            new_users = await self.cache.client.scard(cohort_key)
            metrics: dict[str, dict[str, Any]] = {}
            for retention_day in RETENTION_DAYS:
                target_date = cohort_date + timedelta(days=retention_day)
                metric = await self._retention_metric(
                    cohort_key=cohort_key,
                    new_users=new_users,
                    retention_day=retention_day,
                    target_date=target_date,
                    platform=normalized_platform,
                    today=current_date,
                )
                metrics[str(retention_day)] = {
                    "date": metric.date,
                    "retained_users": metric.retained_users,
                    "rate": metric.rate,
                }

            return {
                "cohort_date": cohort_date_text,
                "platform": normalized_platform,
                "new_users": new_users,
                "retention": metrics,
            }
        except Exception:  # pragma: no cover - defensive for infrastructure issues
            logger.exception("Retention query failed")
            return {
                "cohort_date": cohort_date_text,
                "platform": normalized_platform,
                "new_users": 0,
                "retention": {
                    str(day): {
                        "date": (cohort_date + timedelta(days=day)).isoformat(),
                        "retained_users": None,
                        "rate": None,
                    }
                    for day in RETENTION_DAYS
                },
            }

    async def _retention_metric(
        self,
        *,
        cohort_key: str,
        new_users: int,
        retention_day: int,
        target_date: date,
        platform: str,
        today: date,
    ) -> RetentionMetric:
        target_date_text = target_date.isoformat()
        if target_date > today:
            return RetentionMetric(
                day=retention_day,
                date=target_date_text,
                retained_users=None,
                rate=None,
            )

        active_key = _active_key(target_date_text, platform)
        retained_users = len(await self.cache.client.sinter(cohort_key, active_key))
        rate = round(retained_users / new_users, 4) if new_users else None
        return RetentionMetric(
            day=retention_day,
            date=target_date_text,
            retained_users=retained_users,
            rate=rate,
        )


def get_retention_service() -> RetentionService:
    return RetentionService(get_cache_service())


def should_track_activity(
    device_id: str | None,
    path: str,
    status_code: int | None,
) -> bool:
    if not device_id or not device_id.strip():
        return False
    if status_code is None or status_code >= 500:
        return False
    if path.startswith(("/health", "/ops", "/v1/ops")):
        return False
    return path.startswith("/v1/")


def normalize_retention_platform(value: str | None, *, default: str) -> str:
    if default == "all" and (value is None or value == "all"):
        return "all"
    if not value:
        return "unknown"
    normalized = value.strip().lower()
    if normalized == "all" and default == "all":
        return "all"
    if normalized in TRACKED_PLATFORMS:
        return normalized
    return "unknown"


def _first_seen_key(device_id: str, platform: str = "all") -> str:
    if platform == "all":
        return f"{RETENTION_KEY_PREFIX}:first_seen:{device_id}"
    return f"{RETENTION_KEY_PREFIX}:first_seen:{platform}:{device_id}"


def _cohort_key(date_text: str, platform: str = "all") -> str:
    if platform == "all":
        return f"{RETENTION_KEY_PREFIX}:cohort:{date_text}"
    return f"{RETENTION_KEY_PREFIX}:cohort:{date_text}:{platform}"


def _active_key(date_text: str, platform: str = "all") -> str:
    if platform == "all":
        return f"{RETENTION_KEY_PREFIX}:active:{date_text}"
    return f"{RETENTION_KEY_PREFIX}:active:{date_text}:{platform}"
