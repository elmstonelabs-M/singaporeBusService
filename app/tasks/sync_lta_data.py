import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from itertools import islice
from typing import Any

from sqlalchemy import delete

from app.clients.lta_client import get_lta_client
from app.core.database import SessionLocal
from app.models.bus_route import BusRoute
from app.models.bus_service import BusService
from app.models.bus_stop import BusStop
from app.models.static_data_state import StaticDataState
from app.utils.time_utils import singapore_now

STATIC_DATA_STATE_KEY = "current"


async def _consume_pages(fetcher: Callable[[int], Awaitable[list[dict]]]) -> list[dict]:
    items: list[dict] = []
    skip = 0
    while True:
        page = await fetcher(skip)
        if not page:
            break
        items.extend(page)
        if len(page) < 500:
            break
        skip += 500
    return items


def _batched(items: list[dict], batch_size: int = 500) -> list[list[dict]]:
    iterator = iter(items)
    batches: list[list[dict]] = []
    while batch := list(islice(iterator, batch_size)):
        batches.append(batch)
    return batches


def _normalize_bus_stops(rows: list[dict]) -> list[dict[str, Any]]:
    return [
        {
            "bus_stop_code": row["BusStopCode"],
            "road_name": row["RoadName"],
            "description": row["Description"],
            "latitude": float(row["Latitude"]),
            "longitude": float(row["Longitude"]),
            "search_text": " ".join(
                [row["BusStopCode"], row["RoadName"], row["Description"]]
            ).lower(),
        }
        for row in rows
    ]


def _normalize_bus_routes(rows: list[dict]) -> list[dict[str, Any]]:
    return [
        {
            "service_no": row["ServiceNo"],
            "operator": row.get("Operator"),
            "direction": int(row["Direction"]),
            "stop_sequence": int(row["StopSequence"]),
            "bus_stop_code": row["BusStopCode"],
            "distance_km": str(row["Distance"]) if row.get("Distance") is not None else None,
            "wd_first_bus": row.get("WD_FirstBus"),
            "wd_last_bus": row.get("WD_LastBus"),
            "sat_first_bus": row.get("SAT_FirstBus"),
            "sat_last_bus": row.get("SAT_LastBus"),
            "sun_first_bus": row.get("SUN_FirstBus"),
            "sun_last_bus": row.get("SUN_LastBus"),
        }
        for row in rows
    ]


def _normalize_bus_services(rows: list[dict]) -> list[dict[str, Any]]:
    return [
        {
            "service_no": row["ServiceNo"],
            "operator": row.get("Operator"),
            "direction": int(row["Direction"]),
            "category": row.get("Category"),
            "origin_code": row.get("OriginCode"),
            "destination_code": row.get("DestinationCode"),
            "am_peak_freq": row.get("AM_Peak_Freq"),
            "am_offpeak_freq": row.get("AM_Offpeak_Freq"),
            "pm_peak_freq": row.get("PM_Peak_Freq"),
            "pm_offpeak_freq": row.get("PM_Offpeak_Freq"),
            "loop_desc": row.get("LoopDesc"),
        }
        for row in rows
    ]


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported type for JSON encoding: {type(value)!r}")


def _package_checksum(
    bus_stops: list[dict[str, Any]],
    bus_routes: list[dict[str, Any]],
    bus_services: list[dict[str, Any]],
) -> str:
    payload = {
        "bus_stops": bus_stops,
        "bus_routes": bus_routes,
        "bus_services": bus_services,
    }
    encoded = json.dumps(payload, sort_keys=True, default=_json_default).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


async def _upsert_bus_stops(session, items: list[dict[str, Any]]) -> None:
    for item in items:
        bus_stop = await session.get(BusStop, item["bus_stop_code"])
        if bus_stop is None:
            session.add(BusStop(**item))
            continue

        bus_stop.road_name = item["road_name"]
        bus_stop.description = item["description"]
        bus_stop.latitude = item["latitude"]
        bus_stop.longitude = item["longitude"]
        bus_stop.search_text = item["search_text"]
    await session.commit()


async def _replace_bus_routes(session, items: list[dict[str, Any]]) -> None:
    await session.execute(delete(BusRoute))
    await session.commit()
    for batch in _batched(items):
        for item in batch:
            session.add(
                BusRoute(
                    service_no=item["service_no"],
                    operator=item["operator"],
                    direction=item["direction"],
                    stop_sequence=item["stop_sequence"],
                    bus_stop_code=item["bus_stop_code"],
                    distance_km=item["distance_km"],
                    wd_first_bus=item["wd_first_bus"],
                    wd_last_bus=item["wd_last_bus"],
                    sat_first_bus=item["sat_first_bus"],
                    sat_last_bus=item["sat_last_bus"],
                    sun_first_bus=item["sun_first_bus"],
                    sun_last_bus=item["sun_last_bus"],
                )
            )
        await session.commit()


async def _replace_bus_services(session, items: list[dict[str, Any]]) -> None:
    await session.execute(delete(BusService))
    await session.commit()
    for batch in _batched(items):
        for item in batch:
            session.add(
                BusService(
                    service_no=item["service_no"],
                    operator=item["operator"],
                    direction=item["direction"],
                    category=item["category"],
                    origin_code=item["origin_code"],
                    destination_code=item["destination_code"],
                    am_peak_freq=item["am_peak_freq"],
                    am_offpeak_freq=item["am_offpeak_freq"],
                    pm_peak_freq=item["pm_peak_freq"],
                    pm_offpeak_freq=item["pm_offpeak_freq"],
                    loop_desc=item["loop_desc"],
                )
            )
        await session.commit()


async def sync_all() -> dict[str, Any]:
    client = get_lta_client()
    raw_bus_stops = await _consume_pages(client.get_bus_stops)
    raw_bus_routes = await _consume_pages(client.get_bus_routes)
    raw_bus_services = await _consume_pages(client.get_bus_services)

    bus_stops = _normalize_bus_stops(raw_bus_stops)
    bus_routes = _normalize_bus_routes(raw_bus_routes)
    bus_services = _normalize_bus_services(raw_bus_services)
    checksum = _package_checksum(bus_stops, bus_routes, bus_services)

    async with SessionLocal() as session:
        state = await session.get(StaticDataState, STATIC_DATA_STATE_KEY)
        if state is not None and state.checksum == checksum:
            return {
                "bus_stops": len(bus_stops),
                "bus_routes": len(bus_routes),
                "bus_services": len(bus_services),
                "changed": False,
                "version": state.version,
            }

        await _upsert_bus_stops(session, bus_stops)
        await _replace_bus_routes(session, bus_routes)
        await _replace_bus_services(session, bus_services)

        generated_at = singapore_now()
        version = generated_at.isoformat()
        if state is None:
            state = StaticDataState(
                key=STATIC_DATA_STATE_KEY,
                version=version,
                checksum=checksum,
                generated_at=generated_at,
            )
            session.add(state)
        else:
            state.version = version
            state.checksum = checksum
            state.generated_at = generated_at
        await session.commit()

    return {
        "bus_stops": len(bus_stops),
        "bus_routes": len(bus_routes),
        "bus_services": len(bus_services),
        "changed": True,
        "version": version,
    }


def main() -> None:
    result = asyncio.run(sync_all())
    print(result)


if __name__ == "__main__":
    main()
