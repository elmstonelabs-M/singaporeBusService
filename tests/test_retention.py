from datetime import date

from app.core.config import get_settings
from app.services.retention_service import RetentionService


async def test_retention_tracks_new_users_and_daily_activity(cache_service) -> None:
    service = RetentionService(cache=cache_service)

    await service.track_activity(
        "device-1",
        "/v1/home",
        200,
        activity_date=date(2026, 6, 26),
    )
    await service.track_activity(
        "device-1",
        "/v1/bus-stops/search",
        200,
        activity_date=date(2026, 6, 26),
    )
    await service.track_activity(
        "device-1",
        "/v1/home",
        200,
        activity_date=date(2026, 6, 27),
    )

    first_seen = await cache_service.client.get("retention:first_seen:device-1")
    cohort_count = await cache_service.client.scard("retention:cohort:2026-06-26")
    first_day_active = await cache_service.client.scard("retention:active:2026-06-26")
    second_day_active = await cache_service.client.scard("retention:active:2026-06-27")

    assert first_seen == "2026-06-26"
    assert cohort_count == 1
    assert first_day_active == 1
    assert second_day_active == 1


async def test_retention_tracks_platform_groups(cache_service) -> None:
    service = RetentionService(cache=cache_service)

    await service.track_activity(
        "ios-device",
        "/v1/home",
        200,
        device_platform="ios",
        activity_date=date(2026, 6, 26),
    )
    await service.track_activity(
        "android-device",
        "/v1/home",
        200,
        device_platform="android",
        activity_date=date(2026, 6, 26),
    )
    await service.track_activity(
        "unknown-device",
        "/v1/home",
        200,
        device_platform=None,
        activity_date=date(2026, 6, 26),
    )
    await service.track_activity(
        "other-device",
        "/v1/home",
        200,
        device_platform="web",
        activity_date=date(2026, 6, 26),
    )
    await service.track_activity(
        "ios-device",
        "/v1/home",
        200,
        device_platform="ios",
        activity_date=date(2026, 6, 27),
    )

    ios_payload = await service.get_retention_range(
        date(2026, 6, 26),
        date(2026, 6, 26),
        platform="ios",
        today=date(2026, 6, 27),
    )
    unknown_payload = await service.get_retention_range(
        date(2026, 6, 26),
        date(2026, 6, 26),
        platform="unknown",
        today=date(2026, 6, 27),
    )

    assert ios_payload["platform"] == "ios"
    assert ios_payload["rows"][0]["new_users"] == 1
    assert ios_payload["rows"][0]["retention"]["1"]["retained_users"] == 1
    assert unknown_payload["platform"] == "unknown"
    assert unknown_payload["rows"][0]["new_users"] == 2


async def test_retention_ignores_missing_device_ops_and_server_errors(cache_service) -> None:
    service = RetentionService(cache=cache_service)

    await service.track_activity(None, "/v1/home", 200, activity_date=date(2026, 6, 26))
    await service.track_activity("device-1", "/v1/ops/logs", 200, activity_date=date(2026, 6, 26))
    await service.track_activity("device-2", "/v1/home", 500, activity_date=date(2026, 6, 26))

    assert await cache_service.client.keys("retention:*") == []


async def test_retention_range_returns_requested_columns(cache_service) -> None:
    service = RetentionService(cache=cache_service)

    await service.track_activity(
        "device-1",
        "/v1/home",
        200,
        activity_date=date(2026, 6, 26),
    )
    await service.track_activity(
        "device-2",
        "/v1/home",
        200,
        activity_date=date(2026, 6, 26),
    )
    await service.track_activity(
        "device-1",
        "/v1/home",
        200,
        activity_date=date(2026, 6, 27),
    )

    payload = await service.get_retention_range(
        date(2026, 6, 26),
        date(2026, 6, 26),
        today=date(2026, 6, 27),
    )

    row = payload["rows"][0]
    assert payload["retention_days"] == [1, 2, 3, 4, 5, 6, 7, 15, 30]
    assert row["new_users"] == 2
    assert row["retention"]["1"] == {
        "date": "2026-06-27",
        "retained_users": 1,
        "rate": 0.5,
    }
    assert row["retention"]["2"] == {
        "date": "2026-06-28",
        "retained_users": None,
        "rate": None,
    }


async def test_retention_range_returns_engagement_and_cohort_detail(cache_service) -> None:
    service = RetentionService(cache=cache_service)

    await service.track_activity("device-1", "/v1/home", 200, activity_date=date(2026, 6, 1))
    await service.track_activity("device-2", "/v1/home", 200, activity_date=date(2026, 6, 2))
    await service.track_activity("device-1", "/v1/home", 200, activity_date=date(2026, 6, 3))
    await service.track_activity("device-1", "/v1/home", 200, activity_date=date(2026, 6, 8))
    await service.track_activity("device-3", "/v1/home", 200, activity_date=date(2026, 6, 8))

    payload = await service.get_retention_range(
        date(2026, 6, 1),
        date(2026, 6, 8),
        today=date(2026, 6, 8),
    )

    overview = payload["engagement"]["overview"]
    assert overview == {
        "date": "2026-06-08",
        "dau": 2,
        "wau": 3,
        "mau": 3,
        "dau_mau_rate": 0.6667,
        "wau_mau_rate": 1.0,
        "new_users": 1,
    }
    first_cohort = payload["rows"][0]
    assert first_cohort["detail"] == {
        "install_date": "2026-06-01",
        "new_users": 1,
        "d1_rate": 0.0,
        "d3_rate": 0.0,
        "d7_rate": 1.0,
        "current_active_users": 1,
        "average_active_days": 3.0,
        "latest_active_date": "2026-06-08",
    }


async def test_ops_retention_requires_token(api_client, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ops_log_token", "secret")

    response = await api_client.get("/v1/ops/retention")

    assert response.status_code == 403


async def test_ops_retention_returns_retention_rows(api_client, cache_service, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ops_log_token", "secret")
    service = RetentionService(cache=cache_service)
    await service.track_activity(
        "device-1",
        "/v1/home",
        200,
        activity_date=date(2026, 6, 26),
    )

    response = await api_client.get(
        "/v1/ops/retention?start_date=2026-06-26&end_date=2026-06-26",
        headers={"X-Ops-Token": "secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["retention_days"] == [1, 2, 3, 4, 5, 6, 7, 15, 30]
    assert body["rows"][0]["cohort_date"] == "2026-06-26"
    assert body["rows"][0]["new_users"] == 1


async def test_ops_retention_filters_by_platform(api_client, cache_service, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ops_log_token", "secret")
    service = RetentionService(cache=cache_service)
    await service.track_activity(
        "ios-device",
        "/v1/home",
        200,
        device_platform="ios",
        activity_date=date(2026, 6, 26),
    )
    await service.track_activity(
        "android-device",
        "/v1/home",
        200,
        device_platform="android",
        activity_date=date(2026, 6, 26),
    )

    response = await api_client.get(
        "/v1/ops/retention?start_date=2026-06-26&end_date=2026-06-26&platform=ios",
        headers={"X-Ops-Token": "secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["platform"] == "ios"
    assert body["platforms"] == ["all", "ios", "android", "unknown"]
    assert body["rows"][0]["new_users"] == 1
    assert body["engagement"]["overview"]["dau"] == 1
    assert body["engagement"]["rows"][0]["new_users"] == 1


async def test_ops_retention_page_renders_platform_filter(api_client, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ops_log_token", "secret")

    response = await api_client.get(
        "/ops/retention?token=secret&platform=unknown",
    )

    assert response.status_code == 200
    assert "Retention & Engagement" in response.text
    assert 'name="platform"' in response.text
    assert '<option value="unknown" selected>Unknown</option>' in response.text
    assert "Active Users Trend" in response.text
    assert "Daily Active Statistics" in response.text
    assert "Cohort Retention" in response.text
    assert 'id="cohort-drawer"' in response.text
    assert "&#26597;&#35810;" in response.text


async def test_middleware_tracks_device_activity_without_changing_response(
    api_client,
    cache_service,
) -> None:
    response = await api_client.get(
        "/v1/static-data/version",
        headers={"X-Device-Id": "device-from-header"},
    )

    assert response.status_code == 200
    assert await cache_service.client.get("retention:first_seen:device-from-header") is not None


async def test_middleware_tracks_device_platform(api_client, cache_service) -> None:
    response = await api_client.get(
        "/v1/static-data/version",
        headers={
            "X-Device-Id": "ios-device-from-header",
            "X-Device-Platform": "ios",
        },
    )

    assert response.status_code == 200
    assert await cache_service.client.get(
        "retention:first_seen:ios:ios-device-from-header"
    ) is not None
