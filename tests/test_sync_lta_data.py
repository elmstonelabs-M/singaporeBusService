import uuid

from app.models import BusStop, FavoriteGroup, FavoriteItem, User
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

    monkeypatch.setattr(sync_lta_data, "get_lta_client", lambda: FakeStaticDataClient())
    monkeypatch.setattr(sync_lta_data, "SessionLocal", lambda: FakeSessionLocal(db_session))

    count = await sync_lta_data.sync_bus_stops()

    assert count == 1

    refreshed_bus_stop = await db_session.get(BusStop, "03501")
    refreshed_favorite = await db_session.get(FavoriteItem, favorite.id)

    assert refreshed_bus_stop is not None
    assert refreshed_bus_stop.road_name == "Updated Road"
    assert refreshed_bus_stop.description == "Updated Stop"
    assert refreshed_favorite is not None
    assert refreshed_favorite.bus_stop_code == "03501"
