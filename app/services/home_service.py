from app.core.cache import CacheService
from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.favorite import FavoriteGroupView, FavoriteItemView
from app.schemas.home import HomePayload
from app.services.arrival_service import ArrivalService
from app.services.bus_stop_service import BusStopService
from app.services.favorite_service import FavoriteService
from app.utils.time_utils import singapore_now

settings = get_settings()


class HomeService:
    def __init__(
        self,
        favorite_service: FavoriteService,
        arrival_service: ArrivalService,
        bus_stop_service: BusStopService,
        cache: CacheService,
    ) -> None:
        self.favorite_service = favorite_service
        self.arrival_service = arrival_service
        self.bus_stop_service = bus_stop_service
        self.cache = cache

    async def get_home(
        self,
        user_device_id: str,
        lat: float | None,
        lng: float | None,
    ) -> HomePayload:
        cache_key = self._cache_key(user_device_id, lat, lng)
        cached = await self.cache.get_json(cache_key)
        if isinstance(cached, dict):
            return HomePayload.model_validate(cached)

        now = singapore_now()
        groups = await self.favorite_service.list_groups(user_device_id)
        group_views: list[FavoriteGroupView] = []
        for group in groups:
            items = await self.favorite_service.list_items(group.id)
            item_views: list[FavoriteItemView] = []
            group_bus_stop_code: str | None = None
            group_latitude: float | None = None
            group_longitude: float | None = None
            for item in items:
                bus_stop = await self.bus_stop_service.get_by_code(
                    item.bus_stop_code,
                    user_device_id=user_device_id,
                )
                if group_bus_stop_code is None:
                    group_bus_stop_code = item.bus_stop_code
                    if bus_stop is not None:
                        group_latitude = bus_stop.latitude
                        group_longitude = bus_stop.longitude
                try:
                    arrivals = await self.arrival_service.get_arrivals(
                        bus_stop_code=item.bus_stop_code,
                        service_no=item.service_no,
                        user_device_id=user_device_id,
                    )
                    service = (
                        arrivals["data"]["services"][0]
                        if arrivals["data"]["services"]
                        else None
                    )
                except AppError:
                    service = None
                item_views.append(
                    FavoriteItemView(
                        id=item.id,
                        favorite_id=item.id,
                        group_id=group.id,
                        group_name=group.name,
                        bus_stop_code=item.bus_stop_code,
                        description=(
                            bus_stop.description if bus_stop is not None else item.bus_stop_code
                        ),
                        display_name=(
                            bus_stop.display_name if bus_stop is not None else item.bus_stop_code
                        ),
                        road_name=(bus_stop.road_name if bus_stop is not None else ""),
                        service_no=item.service_no,
                        is_favorite=True,
                        display_order=item.display_order,
                        arrivals=(service or {}).get("arrivals", []),
                    )
                )
            group_views.append(
                FavoriteGroupView(
                    id=group.id,
                    group_id=group.id,
                    name=group.name,
                    emoji=group.emoji,
                    display_order=group.display_order,
                    bus_stop_code=group_bus_stop_code,
                    latitude=group_latitude,
                    longitude=group_longitude,
                    items=item_views,
                )
            )

        nearby = []
        location_label = None
        if lat is not None and lng is not None:
            nearby = await self.bus_stop_service.nearby(
                lat=lat,
                lng=lng,
                user_device_id=user_device_id,
            )
            if nearby:
                location_label = f"{nearby[0].display_name}, Singapore"

        payload = HomePayload(
            location_label=location_label,
            updated_at=now,
            favorite_groups=group_views,
            nearby_bus_stops=nearby,
        )
        await self.cache.set_json(
            cache_key,
            payload.model_dump(mode="json"),
            settings.default_home_cache_ttl_seconds,
        )
        return payload

    @staticmethod
    def _cache_key(user_device_id: str, lat: float | None, lng: float | None) -> str:
        lat_part = "none" if lat is None else f"{lat:.3f}"
        lng_part = "none" if lng is None else f"{lng:.3f}"
        return f"home:{user_device_id}:{lat_part}:{lng_part}"
