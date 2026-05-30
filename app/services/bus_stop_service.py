import math

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheService
from app.core.config import get_settings
from app.models.bus_stop import BusStop
from app.schemas.bus_stop import BusStopItem
from app.services.bus_stop_alias_service import BusStopAliasService
from app.services.bus_stop_catalog import BusStopSnapshot, bus_stop_catalog
from app.utils.geo import haversine_distance_m

settings = get_settings()


class BusStopService:
    def __init__(self, cache: CacheService, db: AsyncSession) -> None:
        self.cache = cache
        self.db = db
        self.alias_service = BusStopAliasService(db)

    async def search(
        self,
        query: str,
        limit: int = 20,
        user_device_id: str | None = None,
    ) -> list[BusStopItem]:
        normalized_query = query.strip()
        key = f"search:{normalized_query.lower()}:{limit}"
        cached = await self.cache.get_json(key)
        alias_map = await self.alias_service.get_alias_map(user_device_id)
        if isinstance(cached, list):
            return [
                self._apply_alias(BusStopItem.model_validate(item), alias_map)
                for item in cached
            ]

        items = self._search_from_catalog(normalized_query, limit)
        if not items:
            stmt: Select[tuple[BusStop]] = (
                select(BusStop)
                .where(
                    or_(
                        BusStop.bus_stop_code == normalized_query,
                        BusStop.description.ilike(f"{normalized_query}%"),
                        BusStop.road_name.ilike(f"{normalized_query}%"),
                        BusStop.search_text.ilike(f"%{normalized_query}%"),
                    )
                )
                .limit(limit * 3)
            )
            result = await self.db.execute(stmt)
            rows = result.scalars().all()
            items = [
                self._to_item(row)
                for row in sorted(
                    rows,
                    key=lambda item: self._search_rank(item, normalized_query.lower()),
                )[:limit]
            ]
        await self.cache.set_json(
            key,
            [item.model_dump(mode="json") for item in items],
            settings.default_search_cache_ttl_seconds,
        )
        return [self._apply_alias(item, alias_map) for item in items]

    async def nearby(
        self,
        lat: float,
        lng: float,
        radius: int = 800,
        limit: int = 20,
        user_device_id: str | None = None,
    ) -> list[BusStopItem]:
        key = f"nearby:{lat:.3f}:{lng:.3f}:{radius}:{limit}"
        cached = await self.cache.get_json(key)
        alias_map = await self.alias_service.get_alias_map(user_device_id)
        if isinstance(cached, list):
            return [
                self._apply_alias(BusStopItem.model_validate(item), alias_map)
                for item in cached
            ]

        lat_delta = radius / 111_320
        lng_divisor = max(math.cos(math.radians(lat)) * 111_320, 0.000001)
        lng_delta = radius / lng_divisor

        items = self._nearby_from_catalog(lat, lng, radius, limit, lat_delta, lng_delta)
        if not items:
            result = await self.db.execute(
                select(BusStop).where(
                    and_(
                        BusStop.latitude.between(lat - lat_delta, lat + lat_delta),
                        BusStop.longitude.between(lng - lng_delta, lng + lng_delta),
                    )
                )
            )
            all_stops = result.scalars().all()
            items = []
            for row in all_stops:
                distance = haversine_distance_m(lat, lng, row.latitude, row.longitude)
                if distance <= radius:
                    items.append(
                        self._to_item(row, distance_m=distance, has_arrival_data=True)
                    )
            items.sort(key=lambda item: item.distance_m or 0)
        trimmed = items[:limit]
        await self.cache.set_json(
            key,
            [item.model_dump(mode="json") for item in trimmed],
            settings.default_nearby_cache_ttl_seconds,
        )
        return [self._apply_alias(item, alias_map) for item in trimmed]

    async def get_by_code(
        self,
        bus_stop_code: str,
        user_device_id: str | None = None,
    ) -> BusStopItem | None:
        snapshot = bus_stop_catalog.get_by_code(bus_stop_code)
        if snapshot is not None:
            item = self._to_item(snapshot)
            alias_map = await self.alias_service.get_alias_map(user_device_id)
            return self._apply_alias(item, alias_map)
        result = await self.db.execute(
            select(BusStop).where(BusStop.bus_stop_code == bus_stop_code)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        item = self._to_item(row)
        alias_map = await self.alias_service.get_alias_map(user_device_id)
        return self._apply_alias(item, alias_map)

    @staticmethod
    def _to_item(
        row: BusStop | BusStopSnapshot,
        distance_m: int | None = None,
        has_arrival_data: bool = False,
    ) -> BusStopItem:
        return BusStopItem(
            bus_stop_code=row.bus_stop_code,
            description=row.description,
            display_name=row.description,
            road_name=row.road_name,
            latitude=row.latitude,
            longitude=row.longitude,
            distance_m=distance_m,
            distance_label=BusStopService._distance_label(distance_m),
            has_arrival_data=has_arrival_data,
        )

    @staticmethod
    def _apply_alias(item: BusStopItem, alias_map: dict[str, str]) -> BusStopItem:
        alias = alias_map.get(item.bus_stop_code)
        if not alias:
            return item
        return item.model_copy(update={"display_name": alias})

    @staticmethod
    def _search_rank(row: BusStop | BusStopSnapshot, query: str) -> tuple[int, str, str]:
        code = row.bus_stop_code.lower()
        description = row.description.lower()
        road_name = row.road_name.lower()
        if code == query:
            return (0, description, code)
        if description.startswith(query):
            return (1, description, code)
        if road_name.startswith(query):
            return (2, road_name, code)
        return (3, description, code)

    @staticmethod
    def _distance_label(distance_m: int | None) -> str | None:
        if distance_m is None:
            return None
        if distance_m < 1000:
            return f"{distance_m}m"
        return f"{distance_m / 1000:.1f}km"

    def _search_from_catalog(self, query: str, limit: int) -> list[BusStopItem]:
        if not bus_stop_catalog.is_loaded():
            return []
        lowered_query = query.lower()
        rows = [
            row
            for row in bus_stop_catalog.all()
            if (
                row.bus_stop_code == query
                or row.description.lower().startswith(lowered_query)
                or row.road_name.lower().startswith(lowered_query)
                or lowered_query in row.search_text.lower()
            )
        ]
        return [
            self._to_item(row)
            for row in sorted(rows, key=lambda item: self._search_rank(item, lowered_query))[
                :limit
            ]
        ]

    def _nearby_from_catalog(
        self,
        lat: float,
        lng: float,
        radius: int,
        limit: int,
        lat_delta: float,
        lng_delta: float,
    ) -> list[BusStopItem]:
        if not bus_stop_catalog.is_loaded():
            return []
        items: list[BusStopItem] = []
        for row in bus_stop_catalog.all():
            if not (lat - lat_delta <= row.latitude <= lat + lat_delta):
                continue
            if not (lng - lng_delta <= row.longitude <= lng + lng_delta):
                continue
            distance = haversine_distance_m(lat, lng, row.latitude, row.longitude)
            if distance <= radius:
                items.append(self._to_item(row, distance_m=distance, has_arrival_data=True))
        items.sort(key=lambda item: item.distance_m or 0)
        return items[:limit]
