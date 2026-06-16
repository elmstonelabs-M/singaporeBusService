from __future__ import annotations

import json
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.utils.time_utils import SINGAPORE_TZ

LOG_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S,%f"
MAX_LOG_LIMIT = 500
DEFAULT_LOG_LIMIT = 100

_BUS_STOP_ARRIVALS_RE = re.compile(r"^/v1/bus-stops/[^/]+/arrivals$")
_BUS_STOP_RE = re.compile(r"^/v1/bus-stops/[^/]+$")
_FAVORITE_RE = re.compile(r"^/v1/favorites/[^/]+$")
_FAVORITE_GROUP_RE = re.compile(r"^/v1/favorite-groups/[^/]+$")


@dataclass(frozen=True)
class ParsedLogLine:
    raw: str
    timestamp_utc: datetime | None
    timestamp_local: datetime | None
    level: str | None
    logger: str | None
    record: dict | None


def clamp_log_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LOG_LIMIT
    return min(max(limit, 1), MAX_LOG_LIMIT)


def get_log_files(log_file_path: str | None) -> list[Path]:
    if not log_file_path:
        return []

    path = Path(log_file_path)
    candidates = path.parent.glob(f"{path.stem}-????-??-??{path.suffix}")
    return sorted((candidate for candidate in candidates if candidate.exists()), key=lambda p: p.name)


def read_recent_arrivals_log_lines(
    log_file_path: str | None,
    limit: int = DEFAULT_LOG_LIMIT,
) -> list[str]:
    bounded_limit = clamp_log_limit(limit)
    recent_lines: deque[str] = deque(maxlen=bounded_limit)
    today_log = get_today_log_file(log_file_path)
    if today_log is not None and today_log.exists():
        with today_log.open("r", encoding="utf-8", errors="replace") as file:
            for line in file:
                raw_line = line.rstrip("\r\n")
                parsed = parse_log_line(raw_line)
                path = parsed.record.get("path") if parsed.record else None
                if isinstance(path, str) and is_bus_stop_arrivals_path(path):
                    recent_lines.append(raw_line)
    return list(recent_lines)


def get_today_log_file(log_file_path: str | None) -> Path | None:
    if not log_file_path:
        return None

    path = Path(log_file_path)
    today = datetime.now(SINGAPORE_TZ).date().isoformat()
    return path.with_name(f"{path.stem}-{today}{path.suffix}")


def build_today_usage_summary(log_file_path: str | None) -> dict:
    today = datetime.now(SINGAPORE_TZ).date()
    request_count = 0
    error_count = 0
    client_error_count = 0
    server_error_count = 0
    clients: set[str] = set()
    devices: set[str] = set()
    platforms: set[str] = set()
    platform_counts: Counter[str] = Counter()
    platform_clients: dict[str, set[str]] = defaultdict(set)
    platform_devices: dict[str, set[str]] = defaultdict(set)
    endpoint_counts: Counter[str] = Counter()
    endpoint_clients: dict[str, set[str]] = defaultdict(set)
    endpoint_devices: dict[str, set[str]] = defaultdict(set)
    device_endpoint_counts: Counter[tuple[str, str]] = Counter()

    for raw_line in _iter_log_lines(log_file_path):
        parsed = parse_log_line(raw_line)
        if parsed.timestamp_local is None or parsed.timestamp_local.date() != today:
            continue
        if not parsed.record:
            continue

        path = parsed.record.get("path")
        if not isinstance(path, str) or not is_bus_stop_arrivals_path(path):
            continue

        request_count += 1
        client = parsed.record.get("client")
        if isinstance(client, str) and client:
            clients.add(client)
        device_id = parsed.record.get("device_id")
        if isinstance(device_id, str) and device_id:
            devices.add(device_id)
        device_platform = parsed.record.get("device_platform")
        platform = device_platform if isinstance(device_platform, str) and device_platform else "Unknown"
        if platform != "Unknown":
            platforms.add(platform)

        status_code = parsed.record.get("status_code")
        if isinstance(status_code, int) and 400 <= status_code < 500:
            client_error_count += 1
            error_count += 1
        elif isinstance(status_code, int) and status_code >= 500:
            server_error_count += 1
            error_count += 1
        elif parsed.record.get("error"):
            server_error_count += 1
            error_count += 1

        endpoint = normalize_endpoint_path(path)
        endpoint_counts[endpoint] += 1
        platform_counts[platform] += 1
        if isinstance(client, str) and client:
            endpoint_clients[endpoint].add(client)
            platform_clients[platform].add(client)
        if isinstance(device_id, str) and device_id:
            endpoint_devices[endpoint].add(device_id)
            platform_devices[platform].add(device_id)
            device_endpoint_counts[(device_id, endpoint)] += 1

    endpoints = [
        {
            "endpoint": endpoint,
            "request_count": count,
            "ip_count": len(endpoint_clients[endpoint]),
            "device_count": len(endpoint_devices[endpoint]),
        }
        for endpoint, count in endpoint_counts.most_common(10)
    ]
    device_endpoints = [
        {
            "device_id": device_id,
            "endpoint": endpoint,
            "request_count": count,
        }
        for (device_id, endpoint), count in device_endpoint_counts.most_common(100)
    ]
    platform_stats = [
        {
            "platform": platform,
            "request_count": count,
            "ip_count": len(platform_clients[platform]),
            "device_count": len(platform_devices[platform]),
        }
        for platform, count in platform_counts.most_common()
    ]

    return {
        "date": today.isoformat(),
        "timezone": "Asia/Singapore",
        "request_count": request_count,
        "ip_count": len(clients),
        "device_count": len(devices),
        "platform_count": len(platforms),
        "error_count": error_count,
        "client_error_count": client_error_count,
        "server_error_count": server_error_count,
        "top_endpoints": endpoints,
        "device_endpoints": device_endpoints,
        "platforms": platform_stats,
    }


def parse_log_line(line: str) -> ParsedLogLine:
    timestamp_local = _parse_timestamp(line[:23])
    timestamp_utc = (
        timestamp_local.astimezone(UTC) if timestamp_local is not None else None
    )
    parts = line.split(" ", 3)
    level = parts[2] if len(parts) >= 3 else None
    logger = parts[3].split(" ", 1)[0] if len(parts) >= 4 and " " in parts[3] else None

    record = None
    json_start = line.find("{")
    if json_start >= 0:
        try:
            decoded = json.loads(line[json_start:])
            if isinstance(decoded, dict):
                record = decoded
        except json.JSONDecodeError:
            record = None

    return ParsedLogLine(
        raw=line,
        timestamp_utc=timestamp_utc,
        timestamp_local=timestamp_local,
        level=level,
        logger=logger,
        record=record,
    )


def normalize_endpoint_path(path: str) -> str:
    if is_bus_stop_arrivals_path(path):
        return "/v1/bus-stops/{bus_stop_code}/arrivals"
    if _BUS_STOP_RE.match(path):
        return "/v1/bus-stops/{bus_stop_code}"
    if _FAVORITE_RE.match(path):
        return "/v1/favorites/{favorite_id}"
    if _FAVORITE_GROUP_RE.match(path):
        return "/v1/favorite-groups/{group_id}"
    return path


def is_bus_stop_arrivals_path(path: str) -> bool:
    return _BUS_STOP_ARRIVALS_RE.fullmatch(path) is not None


def _iter_log_lines(log_file_path: str | None):
    for log_file in get_log_files(log_file_path):
        with log_file.open("r", encoding="utf-8", errors="replace") as file:
            yield from file


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, LOG_TIMESTAMP_FORMAT).replace(tzinfo=SINGAPORE_TZ)
    except ValueError:
        return None
