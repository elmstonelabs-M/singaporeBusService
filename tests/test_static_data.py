from decimal import Decimal

from app.models.bus_route import BusRoute
from app.models.bus_service import BusService
from app.models.bus_stop import BusStop


async def test_static_data_version_endpoint(api_client, db_session) -> None:
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

    response = await api_client.get("/v1/static-data/version")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["package_url"] == "/v1/static-data/package"
    assert body["data"]["checksum"].startswith("sha256:")
    assert body["data"]["min_supported_app_version"] == "1.0.0"
    assert body["meta"]["updated_at"] is not None


async def test_dataset_version_endpoint(api_client, db_session) -> None:
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

    response = await api_client.get("/v1/dataset/version")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["database_url"] == "/v1/static-data/package"
    assert len(body["data"]["sha256"]) == 64
    assert body["data"]["force_update"] is False
    assert body["data"]["updated_at"] == body["meta"]["updated_at"]


async def test_static_data_package_endpoint(api_client, db_session) -> None:
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
    db_session.add(
        BusRoute(
            service_no="36",
            operator="SBST",
            direction=1,
            stop_sequence=1,
            bus_stop_code="83139",
            distance_km=Decimal("0.00"),
            wd_first_bus="0500",
            wd_last_bus="2300",
            sat_first_bus="0500",
            sat_last_bus="2300",
            sun_first_bus="0600",
            sun_last_bus="2300",
        )
    )
    db_session.add(
        BusService(
            service_no="36",
            operator="SBST",
            direction=1,
            category="TRUNK",
            origin_code="83139",
            destination_code="65009",
            am_peak_freq="8-10",
            am_offpeak_freq="12-15",
            pm_peak_freq="8-10",
            pm_offpeak_freq="12-15",
            loop_desc=None,
        )
    )
    await db_session.commit()

    response = await api_client.get("/v1/static-data/package")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["version"] == body["meta"]["updated_at"]
    assert body["data"]["generated_at"] == body["meta"]["updated_at"]
    assert body["data"]["bus_stops"][0]["bus_stop_code"] == "83139"
    assert body["data"]["bus_routes"][0]["service_no"] == "36"
    assert body["data"]["bus_routes"][0]["distance_km"] == "0.00"
    assert body["data"]["bus_services"][0]["service_no"] == "36"


async def test_dataset_download_endpoint_returns_static_package(api_client, db_session) -> None:
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

    response = await api_client.get("/v1/dataset/download")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["bus_stops"][0]["bus_stop_code"] == "83139"
