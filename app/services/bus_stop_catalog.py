from dataclasses import dataclass

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.bus_stop import BusStop


@dataclass(frozen=True, slots=True)
class BusStopSnapshot:
    bus_stop_code: str
    road_name: str
    description: str
    latitude: float
    longitude: float
    search_text: str


class BusStopCatalog:
    def __init__(self) -> None:
        self._items_by_code: dict[str, BusStopSnapshot] = {}
        self._items: tuple[BusStopSnapshot, ...] = ()

    async def load(self) -> None:
        async with SessionLocal() as session:
            result = await session.execute(select(BusStop))
            rows = result.scalars().all()

        items = tuple(
            BusStopSnapshot(
                bus_stop_code=row.bus_stop_code,
                road_name=row.road_name,
                description=row.description,
                latitude=row.latitude,
                longitude=row.longitude,
                search_text=row.search_text,
            )
            for row in rows
        )
        self._items = items
        self._items_by_code = {item.bus_stop_code: item for item in items}

    def get_by_code(self, bus_stop_code: str) -> BusStopSnapshot | None:
        return self._items_by_code.get(bus_stop_code)

    def all(self) -> tuple[BusStopSnapshot, ...]:
        return self._items

    def is_loaded(self) -> bool:
        return bool(self._items)


bus_stop_catalog = BusStopCatalog()
