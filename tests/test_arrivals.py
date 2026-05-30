from app.services.arrival_service import ArrivalService


class StubLTAClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0
        self.requested_service_numbers: list[str | None] = []

    async def get_bus_arrival(self, bus_stop_code: str, service_no: str | None = None) -> dict:
        self.calls += 1
        self.requested_service_numbers.append(service_no)
        return self.payload


async def test_arrival_service_uses_cache(cache_service, db_session) -> None:
    payload = {
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
    client = StubLTAClient(payload)
    service = ArrivalService(lta_client=client, cache=cache_service, db=db_session)

    first = await service.get_arrivals("83139")
    second = await service.get_arrivals("83139")

    assert first["data"]["services"][0]["arrivals"][0]["load_color"] == "green"
    assert second["data"]["services"][0]["service_no"] == "36"
    assert client.calls == 1


async def test_arrival_service_filters_service_from_station_cache(cache_service, db_session) -> None:
    payload = {
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
            },
            {
                "ServiceNo": "106",
                "Operator": "SBST",
                "NextBus": {
                    "EstimatedArrival": "2026-05-19T21:15:00+08:00",
                    "Load": "SDA",
                    "Feature": "",
                    "Type": "SD",
                    "Monitored": 1,
                },
            },
        ]
    }
    client = StubLTAClient(payload)
    service = ArrivalService(lta_client=client, cache=cache_service, db=db_session)

    first = await service.get_arrivals("83139", service_no="36")
    second = await service.get_arrivals("83139", service_no="106")

    assert [item["service_no"] for item in first["data"]["services"]] == ["36"]
    assert [item["service_no"] for item in second["data"]["services"]] == ["106"]
    assert client.calls == 1
    assert client.requested_service_numbers == [None]


async def test_batch_arrivals_groups_requests_by_bus_stop(cache_service, db_session) -> None:
    payload = {
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
            },
            {
                "ServiceNo": "106",
                "Operator": "SBST",
                "NextBus": {
                    "EstimatedArrival": "2026-05-19T21:15:00+08:00",
                    "Load": "SDA",
                    "Feature": "",
                    "Type": "SD",
                    "Monitored": 1,
                },
            },
        ]
    }
    client = StubLTAClient(payload)
    service = ArrivalService(lta_client=client, cache=cache_service, db=db_session)

    result = await service.get_batch_arrivals(
        [
            {"bus_stop_code": "83139", "service_no": "36"},
            {"bus_stop_code": "83139", "service_no": "106"},
        ]
    )

    assert [item["service_no"] for item in result["data"]["items"]] == ["36", "106"]
    assert all(item["status"] == "OK" for item in result["data"]["items"])
    assert client.calls == 1
