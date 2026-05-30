import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bus_route import BusRoute
from app.models.bus_service import BusService
from app.models.bus_stop import BusStop
from app.models.static_data_state import StaticDataState
from app.schemas.static_data import (
    StaticBusRouteItem,
    StaticBusServiceItem,
    StaticBusStopItem,
    StaticDataPackagePayload,
    StaticDataVersionPayload,
)
from app.utils.time_utils import singapore_now


class StaticDataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_version_payload(self) -> tuple[StaticDataVersionPayload, datetime]:
        version, checksum, generated_at = await self._version_info()
        return (
            StaticDataVersionPayload(
                version=version,
                package_url="/v1/static-data/package",
                checksum=checksum,
                min_supported_app_version="1.0.0",
            ),
            generated_at,
        )

    async def get_package_payload(self) -> StaticDataPackagePayload:
        version, _, generated_at = await self._version_info()
        return await self._build_package_payload(version, generated_at)

    async def _build_package_payload(
        self,
        version: str,
        generated_at: datetime,
    ) -> StaticDataPackagePayload:

        bus_stops_result = await self.db.execute(
            select(BusStop).order_by(BusStop.bus_stop_code)
        )
        bus_routes_result = await self.db.execute(
            select(BusRoute).order_by(
                BusRoute.service_no,
                BusRoute.direction,
                BusRoute.stop_sequence,
                BusRoute.bus_stop_code,
            )
        )
        bus_services_result = await self.db.execute(
            select(BusService).order_by(BusService.service_no, BusService.direction)
        )

        return StaticDataPackagePayload(
            version=version,
            generated_at=generated_at,
            bus_stops=[
                StaticBusStopItem(
                    bus_stop_code=item.bus_stop_code,
                    road_name=item.road_name,
                    description=item.description,
                    latitude=item.latitude,
                    longitude=item.longitude,
                    search_text=item.search_text,
                )
                for item in bus_stops_result.scalars().all()
            ],
            bus_routes=[
                StaticBusRouteItem(
                    service_no=item.service_no,
                    operator=item.operator,
                    direction=item.direction,
                    stop_sequence=item.stop_sequence,
                    bus_stop_code=item.bus_stop_code,
                    distance_km=item.distance_km,
                    wd_first_bus=item.wd_first_bus,
                    wd_last_bus=item.wd_last_bus,
                    sat_first_bus=item.sat_first_bus,
                    sat_last_bus=item.sat_last_bus,
                    sun_first_bus=item.sun_first_bus,
                    sun_last_bus=item.sun_last_bus,
                )
                for item in bus_routes_result.scalars().all()
            ],
            bus_services=[
                StaticBusServiceItem(
                    service_no=item.service_no,
                    operator=item.operator,
                    direction=item.direction,
                    category=item.category,
                    origin_code=item.origin_code,
                    destination_code=item.destination_code,
                    am_peak_freq=item.am_peak_freq,
                    am_offpeak_freq=item.am_offpeak_freq,
                    pm_peak_freq=item.pm_peak_freq,
                    pm_offpeak_freq=item.pm_offpeak_freq,
                    loop_desc=item.loop_desc,
                )
                for item in bus_services_result.scalars().all()
            ],
        )

    async def _current_version_timestamp(self) -> datetime:
        max_values = []
        for model in (BusStop, BusRoute, BusService):
            result = await self.db.execute(select(func.max(model.updated_at)))
            max_values.append(result.scalar_one_or_none())
        values = [value for value in max_values if value is not None]
        return max(values) if values else singapore_now()

    async def _version_info(self) -> tuple[str, str, datetime]:
        state = await self.db.get(StaticDataState, "current")
        if state is not None:
            return state.version, state.checksum, state.generated_at

        generated_at = await self._current_version_timestamp()
        version = generated_at.isoformat()
        checksum = await self._package_checksum(version, generated_at)
        return version, checksum, generated_at

    async def _package_checksum(self, version: str, generated_at: datetime) -> str:
        package = await self._build_package_payload(version, generated_at)
        payload = package.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True, default=self._json_default).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    @staticmethod
    def _json_default(value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        raise TypeError(f"Unsupported type for JSON encoding: {type(value)!r}")
