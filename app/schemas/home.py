from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.bus_stop import BusStopItem
from app.schemas.favorite import FavoriteGroupView


class HomePayload(BaseModel):
    location_label: str | None = Field(
        default=None,
        description="Resolved location label, usually based on the closest nearby stop.",
    )
    updated_at: datetime = Field(
        description="Timestamp when the home payload was produced.",
    )
    favorite_groups: list[FavoriteGroupView]
    nearby_bus_stops: list[BusStopItem]
