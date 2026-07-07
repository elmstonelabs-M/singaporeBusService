from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterator
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

        engagement = await self.get_engagement_range(
            start_date,
            end_date,
            platform=normalized_platform,
        )
        await self._attach_cohort_details(
            rows,
            start_date=start_date,
            end_date=end_date,
            platform=normalized_platform,
            activity_sets=engagement["activity_sets"],
        )
        engagement.pop("activity_sets", None)

        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timezone": "Asia/Singapore",
            "platform": normalized_platform,
            "platforms": list(RETENTION_PLATFORMS),
            "retention_days": list(RETENTION_DAYS),
            "engagement": engagement,
            "rows": rows,
        }

    async def get_engagement_range(
        self,
        start_date: date,
        end_date: date,
        *,
        platform: str = "all",
    ) -> dict[str, Any]:
        normalized_platform = normalize_retention_platform(platform, default="all")
        preload_start_date = start_date - timedelta(days=29)
        activity_sets = await self._activity_sets(
            preload_start_date,
            end_date,
            normalized_platform,
        )
        new_user_counts = await self._new_user_counts(start_date, end_date, normalized_platform)

        weekly_users: Counter[str] = Counter()
        monthly_users: Counter[str] = Counter()
        rows: list[dict[str, Any]] = []
        cursor = preload_start_date
        while cursor <= end_date:
            active_users = activity_sets.get(cursor, set())
            _add_users(weekly_users, active_users)
            _add_users(monthly_users, active_users)

            _remove_users(weekly_users, activity_sets.get(cursor - timedelta(days=7), set()))
            _remove_users(monthly_users, activity_sets.get(cursor - timedelta(days=30), set()))

            if cursor >= start_date:
                dau = len(active_users)
                wau = len(weekly_users)
                mau = len(monthly_users)
                rows.append(
                    {
                        "date": cursor.isoformat(),
                        "dau": dau,
                        "wau": wau,
                        "mau": mau,
                        "dau_mau_rate": _ratio(dau, mau),
                        "wau_mau_rate": _ratio(wau, mau),
                        "new_users": new_user_counts.get(cursor, 0),
                    }
                )
            cursor += timedelta(days=1)

        overview = rows[-1] if rows else _empty_engagement_row(end_date)
        return {
            "overview": overview,
            "rows": rows,
            "activity_sets": activity_sets,
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

    async def _activity_sets(
        self,
        start_date: date,
        end_date: date,
        platform: str,
    ) -> dict[date, set[str]]:
        dates = list(_date_range(start_date, end_date))
        if not dates:
            return {}

        pipeline = self.cache.client.pipeline(transaction=False)
        for current_date in dates:
            pipeline.smembers(_active_key(current_date.isoformat(), platform))
        results = await pipeline.execute()
        return {
            current_date: set(result or [])
            for current_date, result in zip(dates, results, strict=True)
        }

    async def _new_user_counts(
        self,
        start_date: date,
        end_date: date,
        platform: str,
    ) -> dict[date, int]:
        dates = list(_date_range(start_date, end_date))
        if not dates:
            return {}

        pipeline = self.cache.client.pipeline(transaction=False)
        for current_date in dates:
            pipeline.scard(_cohort_key(current_date.isoformat(), platform))
        results = await pipeline.execute()
        return {
            current_date: int(result or 0)
            for current_date, result in zip(dates, results, strict=True)
        }

    async def _cohort_members(
        self,
        rows: list[dict[str, Any]],
        platform: str,
    ) -> dict[str, set[str]]:
        if not rows:
            return {}

        pipeline = self.cache.client.pipeline(transaction=False)
        for row in rows:
            pipeline.smembers(_cohort_key(row["cohort_date"], platform))
        results = await pipeline.execute()
        return {
            row["cohort_date"]: set(result or [])
            for row, result in zip(rows, results, strict=True)
        }

    async def _attach_cohort_details(
        self,
        rows: list[dict[str, Any]],
        *,
        start_date: date,
        end_date: date,
        platform: str,
        activity_sets: dict[date, set[str]],
    ) -> None:
        cohort_members = await self._cohort_members(rows, platform)
        for row in rows:
            install_date = date.fromisoformat(row["cohort_date"])
            members = cohort_members.get(row["cohort_date"], set())
            row["detail"] = _cohort_detail(
                row,
                members=members,
                start_date=max(start_date, install_date),
                end_date=end_date,
                activity_sets=activity_sets,
            )

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


def _cohort_detail(
    row: dict[str, Any],
    *,
    members: set[str],
    start_date: date,
    end_date: date,
    activity_sets: dict[date, set[str]],
) -> dict[str, Any]:
    active_day_counts: Counter[str] = Counter()
    latest_active_by_user: dict[str, date] = {}
    latest_active_date: date | None = None

    cursor = start_date
    while cursor <= end_date:
        active_members = members.intersection(activity_sets.get(cursor, set()))
        if active_members:
            latest_active_date = cursor
            for user_id in active_members:
                active_day_counts[user_id] += 1
                latest_active_by_user[user_id] = cursor
        cursor += timedelta(days=1)

    average_active_days = None
    if members:
        average_active_days = round(sum(active_day_counts.values()) / len(members), 1)

    return {
        "install_date": row["cohort_date"],
        "new_users": row["new_users"],
        "d1_rate": _retention_rate(row, 1),
        "d3_rate": _retention_rate(row, 3),
        "d7_rate": _retention_rate(row, 7),
        "current_active_users": len(latest_active_by_user),
        "average_active_days": average_active_days,
        "latest_active_date": latest_active_date.isoformat() if latest_active_date else None,
    }


def _retention_rate(row: dict[str, Any], day: int) -> float | None:
    metric = row["retention"].get(str(day))
    if not metric:
        return None
    return metric["rate"]


def _empty_engagement_row(row_date: date) -> dict[str, Any]:
    return {
        "date": row_date.isoformat(),
        "dau": 0,
        "wau": 0,
        "mau": 0,
        "dau_mau_rate": None,
        "wau_mau_rate": None,
        "new_users": 0,
    }


def _add_users(counter: Counter[str], users: set[str]) -> None:
    for user_id in users:
        counter[user_id] += 1


def _remove_users(counter: Counter[str], users: set[str]) -> None:
    for user_id in users:
        counter[user_id] -= 1
        if counter[user_id] <= 0:
            del counter[user_id]


def _ratio(numerator: int, denominator: int) -> float | None:
    if not denominator:
        return None
    return round(numerator / denominator, 4)


def _date_range(start_date: date, end_date: date) -> Iterator[date]:
    cursor = start_date
    while cursor <= end_date:
        yield cursor
        cursor += timedelta(days=1)


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
