from app.models.bus_stop import BusStop


async def test_health_endpoint(api_client) -> None:
    response = await api_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["timestamp"].endswith("Z")
    assert "database" not in body
    assert "redis" not in body


async def test_health_head_endpoint(api_client) -> None:
    response = await api_client.head("/health")

    assert response.status_code == 200
    assert response.text == ""


async def test_full_health_endpoint(api_client, monkeypatch) -> None:
    class HealthyCacheService:
        async def ping(self) -> bool:
            return True

    monkeypatch.setattr("app.main.get_cache_service", lambda: HealthyCacheService())

    response = await api_client.get("/health/full")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] is True
    assert body["redis"] is True
    assert body["timestamp"].endswith("Z")


async def test_full_health_head_endpoint(api_client) -> None:
    response = await api_client.head("/health/full")

    assert response.status_code == 200
    assert response.text == ""


async def test_arrivals_endpoint(api_client, db_session, lta_client) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    async def fake_get_bus_arrival(bus_stop_code: str, service_no: str | None = None) -> dict:
        return {
            "Services": [
                {
                    "ServiceNo": "36",
                    "Operator": "SBST",
                    "NextBus": {
                        "EstimatedArrival": "2026-05-19T21:12:00+08:00",
                        "Load": "SEA",
                        "Feature": "WAB",
                        "Type": "DD",
                        "Monitored": 1,
                    },
                    "NextBus2": {},
                    "NextBus3": {},
                }
            ]
        }

    lta_client.get_bus_arrival = fake_get_bus_arrival
    response = await api_client.get(
        "/v1/bus-stops/83139/arrivals?user_device_id=device-arrivals"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["bus_stop_code"] == "83139"
    assert body["data"]["description"] == "Opp Example Stop"
    assert body["data"]["display_name"] == "Opp Example Stop"
    assert body["data"]["services"][0]["service_no"] == "36"
    assert body["data"]["services"][0]["favorite_id"] is None


async def test_arrivals_endpoint_uses_alias_and_favorite_without_cache_leak(
    api_client,
    db_session,
    lta_client,
) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marine Parade Rd",
            description="Opp Example Stop",
            latitude=1.3001,
            longitude=103.9001,
            search_text="83139 marine parade rd opp example stop",
        )
    )
    await db_session.commit()

    async def fake_get_bus_arrival(bus_stop_code: str, service_no: str | None = None) -> dict:
        return {
            "Services": [
                {
                    "ServiceNo": "36",
                    "Operator": "SBST",
                    "NextBus": {
                        "EstimatedArrival": "2026-05-19T21:12:00+08:00",
                        "Load": "SEA",
                        "Feature": "WAB",
                        "Type": "DD",
                        "Monitored": 1,
                    },
                    "NextBus2": {},
                    "NextBus3": {},
                }
            ]
        }

    lta_client.get_bus_arrival = fake_get_bus_arrival

    group_response = await api_client.post(
        "/v1/favorite-groups",
        json={
            "user_device_id": "device-arrival-alias",
            "name": "Home",
            "emoji": "H",
            "display_order": 0,
        },
    )
    group_id = group_response.json()["data"]["id"]

    await api_client.put(
        "/v1/bus-stop-aliases",
        json={
            "user_device_id": "device-arrival-alias",
            "bus_stop_code": "83139",
            "alias": "Office Stop",
        },
    )
    await api_client.post(
        "/v1/favorites",
        json={
            "user_device_id": "device-arrival-alias",
            "group_id": group_id,
            "bus_stop_code": "83139",
            "service_no": "36",
            "display_order": 0,
        },
    )

    aliased_response = await api_client.get(
        "/v1/bus-stops/83139/arrivals?user_device_id=device-arrival-alias"
    )
    plain_response = await api_client.get(
        "/v1/bus-stops/83139/arrivals?user_device_id=device-plain"
    )

    assert aliased_response.status_code == 200
    assert plain_response.status_code == 200

    aliased_body = aliased_response.json()
    plain_body = plain_response.json()

    assert aliased_body["data"]["display_name"] == "Office Stop"
    assert aliased_body["data"]["services"][0]["is_favorite"] is True
    assert aliased_body["data"]["services"][0]["group_name"] == "Home"
    assert aliased_body["data"]["services"][0]["favorite_id"] is not None
    assert plain_body["data"]["display_name"] == "Opp Example Stop"
    assert plain_body["data"]["services"][0]["is_favorite"] is False


async def test_search_endpoint(api_client, db_session) -> None:
    db_session.add(
        BusStop(
            bus_stop_code="83139",
            road_name="Marina Blvd",
            description="Marina Bay Sands",
            latitude=1.2839,
            longitude=103.8607,
            search_text="83139 marina blvd marina bay sands",
        )
    )
    await db_session.commit()

    response = await api_client.get("/v1/bus-stops/search?q=83139&user_device_id=device-1")
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["bus_stop_code"] == "83139"
