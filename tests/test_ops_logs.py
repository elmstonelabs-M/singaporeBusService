import json
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app


async def test_ops_logs_requires_token(api_client, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ops_log_token", "secret")
    monkeypatch.setattr(settings, "log_file_path", "missing.log")

    response = await api_client.get("/v1/ops/logs")

    assert response.status_code == 403


async def test_ops_logs_returns_recent_lines_and_today_usage(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "app.log"
    today_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    yesterday_utc = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S,%f")[
        :-3
    ]
    log_path.write_text(
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
    today_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    log_path.write_text(
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
