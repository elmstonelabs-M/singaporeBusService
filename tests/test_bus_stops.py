from app.models.bus_stop import BusStop
from app.services.bus_stop_service import BusStopService


async def test_search_and_nearby(db_session, cache_service) -> None:
    db_session.add_all(
        [
            BusStop(
                bus_stop_code="83139",
                road_name="Marina Blvd",
                description="Marina Bay Sands",
                latitude=1.2839,
                longitude=103.8607,
                search_text="83139 marina blvd marina bay sands",
            ),
            BusStop(
                bus_stop_code="65009",
                road_name="Somerset Rd",
                description="Opp Somerset Stn",
                latitude=1.3000,
                longitude=103.8390,
                search_text="65009 somerset rd opp somerset stn",
            ),
        ]
    )
    await db_session.commit()

    service = BusStopService(cache=cache_service, db=db_session)
    search_results = await service.search("Marina", user_device_id="device-1")
    nearby_results = await service.nearby(
        1.2839,
        103.8607,
        radius=200,
        limit=10,
        user_device_id="device-1",
    )

    assert search_results[0].bus_stop_code == "83139"
    assert nearby_results[0].bus_stop_code == "83139"
    assert nearby_results[0].distance_label is not None
