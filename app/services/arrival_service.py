from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.lta_client import LTAClient
from app.core.cache import CacheService
from app.core.config import get_settings
from app.core.errors import AppError, ExternalServiceError
from app.models.favorite import FavoriteGroup, FavoriteItem
from app.models.user import User
from app.services.bus_stop_service import BusStopService
from app.services.favorite_service import FavoriteService
from app.services.normalizers import (
    is_wheelchair_accessible,
    map_bus_type,
    map_load,
    normalize_arrival_time,
)
from app.services.operating_service import OperatingService
from app.utils.time_utils import singapore_now

settings = get_settings()


class ArrivalService:
    def __init__(
        self,
        lta_client: LTAClient,
        cache: CacheService,
        db: AsyncSession,
        operating_service: OperatingService | None = None,
        bus_stop_service: BusStopService | None = None,
    ) -> None:
        self.lta_client = lta_client
        self.cache = cache
        self.db = db
        self.operating_service = operating_service or OperatingService(db)
        self.bus_stop_service = bus_stop_service or BusStopService(cache=cache, db=db)
        self.favorite_service = FavoriteService(db)

    async def get_arrivals(
        self,
        bus_stop_code: str,
        service_no: str | None = None,
        user_device_id: str | None = None,
    ) -> dict[str, Any]:
        if not (len(bus_stop_code) == 5 and bus_stop_code.isdigit()):
            raise AppError(
                "INVALID_BUS_STOP_CODE",
                "Bus stop code must be a 5-digit number.",
                422,
            )

        key = self._cache_key(bus_stop_code)
        cached = await self.cache.get_json(key)
        if isinstance(cached, dict):
            filtered = self._filter_service(payload=cached, service_no=service_no)
            return await self._hydrate_payload(filtered, bus_stop_code, user_device_id)

        try:
            payload = await self.lta_client.get_bus_arrival(bus_stop_code)
            normalized = await self._normalize_payload(payload, bus_stop_code)
            await self.cache.set_json(
                key,
                normalized,
                settings.default_arrival_cache_ttl_seconds,
            )
            await self.cache.set_json(
                self._last_good_key(bus_stop_code),
                normalized,
                settings.default_last_good_cache_ttl_seconds,
            )
            filtered = self._filter_service(payload=normalized, service_no=service_no)
            return await self._hydrate_payload(filtered, bus_stop_code, user_device_id)
        except Exception as exc:
            last_good = await self.cache.get_json(
                self._last_good_key(bus_stop_code)
            )
            if isinstance(last_good, dict):
                last_good.setdefault("meta", {})
                last_good["meta"]["stale"] = True
                filtered = self._filter_service(payload=last_good, service_no=service_no)
                return await self._hydrate_payload(
                    filtered,
                    bus_stop_code,
                    user_device_id,
                )
            if isinstance(exc, ExternalServiceError):
                raise
            raise ExternalServiceError(
                "LTA_REQUEST_FAILED",
                "Failed to fetch arrival data.",
            ) from exc

    async def get_batch_arrivals(
        self,
        items: list[dict[str, str]],
        user_device_id: str | None = None,
    ) -> dict[str, Any]:
        now = singapore_now()
        results: list[dict[str, Any]] = []
        grouped: dict[str, list[str]] = {}
        stale = False
        for item in items:
            bus_stop_code = item["bus_stop_code"]
            service_no = item["service_no"]
            grouped.setdefault(bus_stop_code, []).append(service_no)

        for bus_stop_code, service_numbers in grouped.items():
            try:
                station_payload = await self.get_arrivals(
                    bus_stop_code,
                    user_device_id=user_device_id,
                )
                stale = stale or bool(station_payload.get("meta", {}).get("stale"))
                services_by_no = {
                    service["service_no"]: service
                    for service in station_payload.get("data", {}).get("services", [])
                }
                for service_no in service_numbers:
                    service = services_by_no.get(service_no)
                    if service is None:
                        results.append(
                            {
                                "bus_stop_code": bus_stop_code,
                                "service_no": service_no,
                                "status": "NOT_FOUND",
                                "arrivals": [],
                                "error_code": "SERVICE_NOT_FOUND",
                            }
                        )
                        continue
                    results.append(
                        {
                            "bus_stop_code": bus_stop_code,
                            "service_no": service_no,
                            "status": "OK",
                            "arrivals": service.get("arrivals", []),
                        }
                    )
            except AppError as exc:
                for service_no in service_numbers:
                    results.append(
                        {
                            "bus_stop_code": bus_stop_code,
                            "service_no": service_no,
                            "status": "ERROR",
                            "arrivals": [],
                            "error_code": exc.code,
                        }
                    )

        return {
            "data": {
                "updated_at": now.isoformat(),
                "items": results,
            },
            "meta": {
                "updated_at": now.isoformat(),
                "stale": stale,
            },
        }

    async def _normalize_payload(
        self,
        payload: dict[str, Any],
        bus_stop_code: str,
    ) -> dict[str, Any]:
        now = singapore_now()
        services: list[dict[str, Any]] = []

        for service in payload.get("Services", []):
            service_no = service.get("ServiceNo", "")
            arrivals: list[dict[str, Any]] = []
            for index, key in enumerate(("NextBus", "NextBus2", "NextBus3"), start=1):
                bus = service.get(key) or {}
                normalized_time = normalize_arrival_time(bus.get("EstimatedArrival"), now)
                if normalized_time["status"] == "NO_DATA":
                    continue
                arrivals.append(
                    {
                        "sequence": index,
                        "visit_number": index,
                        **normalized_time,
                        **map_load(bus.get("Load")),
                        "wheelchair": is_wheelchair_accessible(bus.get("Feature")),
                        **map_bus_type(bus.get("Type")),
                        "monitored": bus.get("Monitored") == 1,
                        "vehicle_latitude": self._parse_vehicle_coordinate(bus.get("Latitude")),
                        "vehicle_longitude": self._parse_vehicle_coordinate(
                            bus.get("Longitude")
                        ),
                    }
                )

            if not arrivals:
                is_operating = await self.operating_service.is_service_operating_now(
                    bus_stop_code=bus_stop_code,
                    service_no=service_no,
                    now=now,
                )
                arrivals.append(
                    {
                        "sequence": 1,
                        "visit_number": 1,
                        "display": (
                            "No Est. Available" if is_operating else "Not In Operation"
                        ),
                        "minutes": None,
                        "status": "NO_ESTIMATE" if is_operating else "NOT_IN_OPERATION",
                        "load": None,
                        "load_label": None,
                        "load_color": "gray",
                        "wheelchair": False,
                        "bus_type": None,
                        "bus_type_label": None,
                        "monitored": False,
                        "estimated_arrival": None,
                        "vehicle_latitude": None,
                        "vehicle_longitude": None,
                    }
                )

            services.append(
                {
                    "service_no": service_no,
                    "operator": service.get("Operator"),
                    "is_favorite": False,
                    "arrivals": arrivals,
                }
            )

        return {
            "data": {
                "bus_stop_code": bus_stop_code,
                "updated_at": now.isoformat(),
                "services": services,
            },
            "meta": {
                "updated_at": now.isoformat(),
                "stale": False,
            },
        }

    async def _hydrate_payload(
        self,
        payload: dict[str, Any],
        bus_stop_code: str,
        user_device_id: str | None,
    ) -> dict[str, Any]:
        hydrated = deepcopy(payload)
        data = hydrated.setdefault("data", {})

        bus_stop = await self.bus_stop_service.get_by_code(
            bus_stop_code,
            user_device_id=user_device_id,
        )
        if bus_stop is not None:
            data["description"] = bus_stop.description
            data["display_name"] = bus_stop.display_name
            data["road_name"] = bus_stop.road_name
            data["latitude"] = bus_stop.latitude
            data["longitude"] = bus_stop.longitude

        favorite_metadata = await self._favorite_metadata(bus_stop_code, user_device_id)
        for service in data.get("services", []):
            metadata = favorite_metadata.get(service.get("service_no", ""))
            if metadata is None:
                service["is_favorite"] = False
                service["favorite_id"] = None
                service["group_id"] = None
                service["group_name"] = None
                service["display_order"] = None
            else:
                service.update(metadata)

        return hydrated

    async def _favorite_metadata(
        self,
        bus_stop_code: str,
        user_device_id: str | None,
    ) -> dict[str, dict[str, str | int | bool | None]]:
        if not user_device_id:
            return {}
        return await self.favorite_service.get_favorite_metadata_map(
            user_device_id=user_device_id,
            bus_stop_code=bus_stop_code,
        )

    async def _favorite_keys(self, user_device_id: str | None) -> set[tuple[str, str]]:
        if not user_device_id:
            return set()
        result = await self.db.execute(
            select(FavoriteItem.bus_stop_code, FavoriteItem.service_no)
            .join(FavoriteGroup, FavoriteGroup.id == FavoriteItem.group_id)
            .join(User, User.id == FavoriteGroup.user_id)
            .where(User.device_id == user_device_id)
        )
        rows = result.all()
        return {(row[0], row[1]) for row in rows}

    @staticmethod
    def _filter_service(payload: dict[str, Any], service_no: str | None) -> dict[str, Any]:
        if not service_no:
            return payload
        filtered = deepcopy(payload)
        data = filtered.setdefault("data", {})
        services = data.get("services", [])
        data["services"] = [
            service
            for service in services
            if service.get("service_no") == service_no
        ]
        return filtered

    @staticmethod
    def _cache_key(bus_stop_code: str) -> str:
        return f"arrival:{bus_stop_code}"

    @staticmethod
    def _last_good_key(bus_stop_code: str) -> str:
        return f"arrival:last_good:{bus_stop_code}"

    @staticmethod
    def _parse_vehicle_coordinate(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
