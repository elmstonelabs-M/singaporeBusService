from app.models.bus_route import BusRoute
from app.services.arrival_service import ArrivalService


class EmptyArrivalClient:
    async def get_bus_arrival(
        self,
        bus_stop_code: str,
        service_no: str | None = None,
    ) -> dict:
        return {
            "Services": [
                {
                    "ServiceNo": service_no or "36",
                    "Operator": "SBST",
                    "NextBus": {},
                    "NextBus2": {},
                    "NextBus3": {},
                }
            ]
        }


async def test_arrival_service_marks_not_in_operation(cache_service, db_session) -> None:
    db_session.add(
        BusRoute(
            service_no="36",
            operator="SBST",
            direction=1,
            stop_sequence=1,
            bus_stop_code="83139",
            wd_first_bus="0600",
            wd_last_bus="0700",
            sat_first_bus="0600",
            sat_last_bus="0700",
            sun_first_bus="0600",
            sun_last_bus="0700",
        )
    )
    await db_session.commit()

    service = ArrivalService(
        lta_client=EmptyArrivalClient(),
        cache=cache_service,
        db=db_session,
    )
    response = await service.get_arrivals("83139", service_no="36")
    assert response["data"]["services"][0]["arrivals"][0]["status"] in {
        "NO_ESTIMATE",
        "NOT_IN_OPERATION",
    }
