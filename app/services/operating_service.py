from datetime import datetime, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bus_route import BusRoute


class OperatingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def is_service_operating_now(
        self,
        bus_stop_code: str,
        service_no: str,
        now: datetime,
    ) -> bool:
        result = await self.db.execute(
            select(BusRoute)
            .where(BusRoute.bus_stop_code == bus_stop_code)
            .where(BusRoute.service_no == service_no)
            .order_by(BusRoute.direction, BusRoute.stop_sequence)
        )
        routes = list(result.scalars().all())
        if not routes:
            return True

        current_time = now.time()
        for route in routes:
            start_raw, end_raw = self._service_window_for_day(route, now)
            start_time = self._parse_hhmm(start_raw)
            end_time = self._parse_hhmm(end_raw)
            if start_time is None or end_time is None:
                return True
            if self._time_in_range(current_time, start_time, end_time):
                return True
        return False

    @staticmethod
    def _service_window_for_day(route: BusRoute, now: datetime) -> tuple[str | None, str | None]:
        weekday = now.weekday()
        if weekday == 5:
            return route.sat_first_bus, route.sat_last_bus
        if weekday == 6:
            return route.sun_first_bus, route.sun_last_bus
        return route.wd_first_bus, route.wd_last_bus

    @staticmethod
    def _parse_hhmm(value: str | None) -> time | None:
        if not value or len(value) != 4 or not value.isdigit():
            return None
        hour = int(value[:2]) % 24
        minute = int(value[2:])
        if minute > 59:
            return None
        return time(hour=hour, minute=minute)

    @staticmethod
    def _time_in_range(current: time, start: time, end: time) -> bool:
        if start <= end:
            return start <= current <= end
        return current >= start or current <= end
