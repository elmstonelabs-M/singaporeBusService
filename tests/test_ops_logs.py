import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.logging import DailySizeLimitedFileHandler
from app.main import app
from app.services.log_service import get_log_files, parse_log_line, read_recent_log_lines

LOCAL_TZ = ZoneInfo("Asia/Singapore")


async def test_ops_logs_requires_token(api_client, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ops_log_token", "secret")
    monkeypatch.setattr(settings, "log_file_path", "missing.log")

    response = await api_client.get("/v1/ops/logs")

    assert response.status_code == 403


async def test_ops_logs_returns_recent_lines_and_today_usage(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "app.log"
    daily_log_path = tmp_path / f"app-{datetime.now().date().isoformat()}.log"
    today_utc = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    yesterday_utc = (datetime.now(LOCAL_TZ) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S,%f")[
        :-3
    ]
    daily_log_path.write_text(
        "\n".join(
            [
                (
                    f"{yesterday_utc} INFO app.http "
                    + json.dumps(
                        {
                            "path": "/v1/bus-stops/83139/arrivals",
                            "client": "10.0.0.1",
                            "device_id": "device-1",
                            "status_code": 200,
                        }
                    )
                ),
                (
                    f"{today_utc} INFO app.http "
                    + json.dumps(
                            {
                                "path": "/v1/bus-stops/83139/arrivals",
                                "client": "10.0.0.1",
                                "device_id": "device-1",
                                "status_code": 200,
                            }
                    )
                ),
                (
                    f"{today_utc} INFO app.http "
                    + json.dumps(
                        {
                            "path": "/v1/bus-stops/01012/arrivals",
                            "client": "10.0.0.2",
                            "device_id": "device-2",
                            "status_code": 200,
                        }
                    )
                ),
                (
                    f"{today_utc} INFO app.http "
                    + json.dumps(
                        {
                            "path": "/health",
                            "client": "127.0.0.1",
                            "status_code": 200,
                        }
                    )
                ),
                (
                    f"{today_utc} INFO app.http "
                    + json.dumps(
                        {
                            "path": "/v1/static-data/version",
                            "client": "10.0.0.4",
                            "device_id": "device-static",
                            "status_code": 200,
                        }
                    )
                ),
                (
                    f"{today_utc} INFO app.http "
                    + json.dumps(
                        {
                            "path": "/v1/dataset/download",
                            "client": "10.0.0.5",
                            "device_id": "device-dataset",
                            "status_code": 200,
                        }
                    )
                ),
                (
                    f"{today_utc} INFO app.http "
                    + json.dumps(
                        {
                            "path": "/v1/bus-stops/search",
                            "client": "10.0.0.3",
                            "device_id": "device-2",
                            "status_code": 422,
                        }
                    )
                ),
                (
                    f"{today_utc} INFO app.http "
                    + json.dumps(
                        {
                            "path": "/v1/arrivals/batch",
                            "client": "10.0.0.2",
                            "status_code": 500,
                        }
                    )
                ),
            ]
        ),
        encoding="utf-8",
    )
    settings = get_settings()
    monkeypatch.setattr(settings, "ops_log_token", "secret")
    monkeypatch.setattr(settings, "log_file_path", str(log_path))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/v1/ops/logs?limit=2", headers={"X-Ops-Token": "secret"})

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert len(body["lines"]) == 2
    assert body["today"]["request_count"] == 4
    assert body["today"]["ip_count"] == 3
    assert body["today"]["device_count"] == 2
    assert body["today"]["error_count"] == 2
    assert body["today"]["client_error_count"] == 1
    assert body["today"]["server_error_count"] == 1
    assert body["today"]["top_endpoints"][0] == {
        "endpoint": "/v1/bus-stops/{bus_stop_code}/arrivals",
        "request_count": 2,
        "ip_count": 2,
        "device_count": 2,
    }
    assert body["today"]["device_endpoints"] == [
        {
            "device_id": "device-1",
            "endpoint": "/v1/bus-stops/{bus_stop_code}/arrivals",
            "request_count": 1,
        },
        {
            "device_id": "device-2",
            "endpoint": "/v1/bus-stops/{bus_stop_code}/arrivals",
            "request_count": 1,
        },
        {
            "device_id": "device-2",
            "endpoint": "/v1/bus-stops/{bus_stop_code}",
            "request_count": 1,
        },
    ]


async def test_ops_logs_page_renders_summary(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "app.log"
    daily_log_path = tmp_path / f"app-{datetime.now().date().isoformat()}.log"
    today_utc = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    daily_log_path.write_text(
        (
            f"{today_utc} INFO app.http "
            + json.dumps(
                {
                    "path": "/v1/bus-stops/83139/arrivals",
                    "client": "10.0.0.1",
                    "device_id": "device-full-id",
                    "status_code": 200,
                }
            )
        ),
        encoding="utf-8",
    )
    settings = get_settings()
    monkeypatch.setattr(settings, "ops_log_token", "secret")
    monkeypatch.setattr(settings, "log_file_path", str(log_path))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/ops/logs?token=secret")

    assert response.status_code == 200
    assert "Top Endpoints" in response.text
    assert "Device Endpoint Requests" in response.text
    assert "device-full-id" in response.text
    assert "/v1/bus-stops/{bus_stop_code}/arrivals" in response.text


def test_log_files_include_only_daily_files(tmp_path) -> None:
    base_path = tmp_path / "app.log"
    legacy_path = tmp_path / "app.log.1"
    older_daily_path = tmp_path / "app-2026-06-10.log"
    newer_daily_path = tmp_path / "app-2026-06-11.log"
    for path in (base_path, legacy_path, older_daily_path, newer_daily_path):
        path.write_text(path.name, encoding="utf-8")

    assert get_log_files(str(base_path)) == [
        older_daily_path,
        newer_daily_path,
    ]


def test_recent_logs_only_include_today_singapore_file(tmp_path) -> None:
    base_path = tmp_path / "app.log"
    today = datetime.now(LOCAL_TZ).date()
    yesterday_path = tmp_path / f"app-{today - timedelta(days=1)}.log"
    today_path = tmp_path / f"app-{today}.log"
    yesterday_path.write_text("yesterday-old\nyesterday-new\n", encoding="utf-8")
    today_path.write_text("today-old\ntoday-new\n", encoding="utf-8")

    assert read_recent_log_lines(str(base_path), limit=3) == [
        "today-old",
        "today-new",
    ]


def test_daily_log_trim_keeps_newest_complete_lines(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "app.log"
    daily_path = tmp_path / "app-2026-06-11.log"
    daily_path.write_bytes(b"old-line\nmiddle-line\nnew-line\n")
    handler = DailySizeLimitedFileHandler(log_path)

    monkeypatch.setattr("app.core.logging.TRIMMED_DAILY_LOG_BYTES", 18)
    handler._trim_oldest_lines(daily_path)

    assert daily_path.read_bytes() == b"new-line\n"


def test_daily_log_removes_files_older_than_seven_days(tmp_path) -> None:
    log_path = tmp_path / "app.log"
    expired_path = tmp_path / "app-2026-06-04.log"
    retained_path = tmp_path / "app-2026-06-05.log"
    expired_path.write_text("expired", encoding="utf-8")
    retained_path.write_text("retained", encoding="utf-8")
    handler = DailySizeLimitedFileHandler(log_path)

    handler._remove_expired_logs(datetime(2026, 6, 11).date())

    assert not expired_path.exists()
    assert retained_path.exists()


def test_log_timestamp_near_midnight_stays_on_singapore_date() -> None:
    parsed = parse_log_line(
        '2026-06-11 23:59:59,999 INFO app.http {"path": "/v1/bus-stops/17059/arrivals"}'
    )

    assert parsed.timestamp_local is not None
    assert parsed.timestamp_local.isoformat() == "2026-06-11T23:59:59.999000+08:00"
    assert parsed.timestamp_utc is not None
    assert parsed.timestamp_utc.isoformat() == "2026-06-11T15:59:59.999000+00:00"
