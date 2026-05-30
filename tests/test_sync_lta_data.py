import uuid
from datetime import datetime, timedelta

from app.models import BusRoute, BusService, BusStop, FavoriteGroup, FavoriteItem, StaticDataState, User
from app.tasks import sync_lta_data


class FakeStaticDataClient:
    async def get_bus_stops(self, skip: int = 0) -> list[dict[str, object]]:
        if skip > 0:
            return []
        return [
            {
                "BusStopCode": "03501",
                "RoadName": "Updated Road",
                "Description": "Updated Stop",
                "Latitude": "1.3001",
                "Longitude": "103.9001",
            }
        ]


class FakeSessionLocal:
    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


async def test_sync_bus_stops_preserves_favorite_references(db_session, monkeypatch) -> None:
    user = User(id=uuid.uuid4(), device_id="device-1")
    group = FavoriteGroup(id=uuid.uuid4(), user_id=user.id, name="Home", emoji="H", display_order=0)
    bus_stop = BusStop(
        bus_stop_code="03501",
        road_name="Old Road",
        description="Old Stop",
        latitude=1.2,
        longitude=103.8,
        search_text="03501 old road old stop",
    )
    favorite = FavoriteItem(
        id=uuid.uuid4(),
        group_id=group.id,
        bus_stop_code="03501",
        service_no="36",
        display_order=0,
    )
    db_session.add_all([user, group, bus_stop, favorite])
    await db_session.commit()

    rows = await FakeStaticDataClient().get_bus_stops()
    items = sync_lta_data._normalize_bus_stops(rows)

    await sync_lta_data._upsert_bus_stops(db_session, items)

    assert len(items) == 1

    refreshed_bus_stop = await db_session.get(BusStop, "03501")
    refreshed_favorite = await db_session.get(FavoriteItem, favorite.id)

    assert refreshed_bus_stop is not None
    assert refreshed_bus_stop.road_name == "Updated Road"
    assert refreshed_bus_stop.description == "Updated Stop"
    assert refreshed_favorite is not None
    assert refreshed_favorite.bus_stop_code == "03501"


class FakeFullStaticDataClient:
    def __init__(self, description: str = "Updated Stop") -> None:
        self.description = description

    async def get_bus_stops(self, skip: int = 0) -> list[dict[str, object]]:
        if skip > 0:
            return []
        return [
            {
                "BusStopCode": "03501",
                "RoadName": "Updated Road",
                "Description": self.description,
                "Latitude": "1.3001",
                "Longitude": "103.9001",
            }
        ]

    async def get_bus_routes(self, skip: int = 0) -> list[dict[str, object]]:
        if skip > 0:
            return []
        return [
            {
                "ServiceNo": "36",
                "Operator": "SBST",
                "Direction": 1,
                "StopSequence": 1,
                "BusStopCode": "03501",
                "Distance": "0.0",
                "WD_FirstBus": "0500",
                "WD_LastBus": "2300",
                "SAT_FirstBus": "0500",
                "SAT_LastBus": "2300",
                "SUN_FirstBus": "0600",
                "SUN_LastBus": "2300",
            }
        ]

    async def get_bus_services(self, skip: int = 0) -> list[dict[str, object]]:
        if skip > 0:
            return []
        return [
            {
                "ServiceNo": "36",
                "Operator": "SBST",
                "Direction": 1,
                "Category": "TRUNK",
                "OriginCode": "03501",
                "DestinationCode": "65009",
                "AM_Peak_Freq": "8-10",
                "AM_Offpeak_Freq": "12-15",
                "PM_Peak_Freq": "8-10",
                "PM_Offpeak_Freq": "12-15",
                "LoopDesc": None,
            }
        ]


async def test_sync_all_keeps_existing_version_when_checksum_unchanged(db_session, monkeypatch) -> None:
    initial_generated_at = datetime.fromisoformat("2026-05-28T03:00:00+08:00")
    db_session.add(
        StaticDataState(
            key=sync_lta_data.STATIC_DATA_STATE_KEY,
            version="2026-05-28T03:00:00+08:00",
            checksum="placeholder",
            generated_at=initial_generated_at,
        )
    )
    await db_session.commit()

    monkeypatch.setattr(sync_lta_data, "get_lta_client", lambda: FakeFullStaticDataClient())
    monkeypatch.setattr(sync_lta_data, "SessionLocal", lambda: FakeSessionLocal(db_session))

    bus_stops = sync_lta_data._normalize_bus_stops(await FakeFullStaticDataClient().get_bus_stops())
    bus_routes = sync_lta_data._normalize_bus_routes(await FakeFullStaticDataClient().get_bus_routes())
    bus_services = sync_lta_data._normalize_bus_services(await FakeFullStaticDataClient().get_bus_services())
    checksum = sync_lta_data._package_checksum(bus_stops, bus_routes, bus_services)

    state = await db_session.get(StaticDataState, sync_lta_data.STATIC_DATA_STATE_KEY)
    assert state is not None
    state.checksum = checksum
    await db_session.commit()

    result = await sync_lta_data.sync_all()

    refreshed_state = await db_session.get(StaticDataState, sync_lta_data.STATIC_DATA_STATE_KEY)
    assert result["changed"] is False
    assert result["version"] == "2026-05-28T03:00:00+08:00"
    assert refreshed_state is not None
    assert refreshed_state.version == "2026-05-28T03:00:00+08:00"
    assert refreshed_state.generated_at.isoformat() == initial_generated_at.replace(tzinfo=None).isoformat()


async def test_sync_all_updates_version_when_checksum_changes(db_session, monkeypatch) -> None:
    old_generated_at = datetime.fromisoformat("2026-05-28T03:00:00+08:00")
    db_session.add(
        StaticDataState(
            key=sync_lta_data.STATIC_DATA_STATE_KEY,
            version="2026-05-28T03:00:00+08:00",
            checksum="sha256:old",
            generated_at=old_generated_at,
        )
    )
    await db_session.commit()

    monkeypatch.setattr(sync_lta_data, "get_lta_client", lambda: FakeFullStaticDataClient(description="New Stop"))
    monkeypatch.setattr(sync_lta_data, "SessionLocal", lambda: FakeSessionLocal(db_session))

    result = await sync_lta_data.sync_all()

    refreshed_state = await db_session.get(StaticDataState, sync_lta_data.STATIC_DATA_STATE_KEY)
    refreshed_bus_stop = await db_session.get(BusStop, "03501")
    routes = (await db_session.execute(BusRoute.__table__.select())).all()
    services = (await db_session.execute(BusService.__table__.select())).all()

    assert result["changed"] is True
    assert refreshed_state is not None
    assert refreshed_state.version == result["version"]
    assert refreshed_state.version != "2026-05-28T03:00:00+08:00"
    assert refreshed_state.generated_at is not None
    assert refreshed_state.generated_at.isoformat() >= (old_generated_at - timedelta(seconds=1)).replace(
        tzinfo=None
    ).isoformat()
    assert refreshed_bus_stop is not None
    assert refreshed_bus_stop.description == "New Stop"
    assert len(routes) == 1
    assert len(services) == 1
