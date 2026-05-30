from datetime import datetime

from pydantic import BaseModel, Field


class BusStopItem(BaseModel):
    bus_stop_code: str = Field(description="5-digit bus stop code.")
    description: str = Field(description="Official LTA bus stop name.")
    display_name: str = Field(
        description=(
            "User-facing bus stop name. Uses the current user's alias; "
            "user_device_id is required."
        ),
    )
    road_name: str = Field(description="Road name of the bus stop.")
    latitude: float = Field(description="Bus stop latitude.")
    longitude: float = Field(description="Bus stop longitude.")
    distance_m: int | None = Field(
        default=None,
        description="Distance from the queried location in meters.",
    )
    distance_label: str | None = Field(
        default=None,
        description="Frontend-friendly distance label such as 120m or 1.2km.",
    )
    has_arrival_data: bool = Field(
        default=False,
        description="Whether this response was assembled for an arrival-aware context.",
    )


class BusStopAliasUpsert(BaseModel):
    user_device_id: str = Field(description="Client-side stable user device identifier.")
    bus_stop_code: str = Field(description="5-digit bus stop code.")
    alias: str = Field(description="User-defined display alias for this bus stop.")


class BusStopAliasView(BaseModel):
    bus_stop_code: str = Field(description="5-digit bus stop code.")
    alias: str = Field(description="User-defined display alias.")
    updated_at: datetime | None = Field(
        default=None,
        description="Timestamp when the alias was last updated.",
    )


class BusStopListPayload(BaseModel):
    items: list[BusStopItem]


class BusStopAliasListPayload(BaseModel):
    items: list[BusStopAliasView]
