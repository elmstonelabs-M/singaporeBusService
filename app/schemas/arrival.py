from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ArrivalStatus(StrEnum):
    ARRIVING = "ARRIVING"
    ESTIMATED = "ESTIMATED"
    NO_ESTIMATE = "NO_ESTIMATE"
    NOT_IN_OPERATION = "NOT_IN_OPERATION"


class BusLoad(StrEnum):
    SEA = "SEA"
    SDA = "SDA"
    LSD = "LSD"


class LoadColor(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    GRAY = "gray"


class BusType(StrEnum):
    SD = "SD"
    DD = "DD"
    BD = "BD"


class ArrivalItem(BaseModel):
    sequence: int = Field(description="Arrival slot index from LTA: 1, 2, or 3.")
    display: str | None = Field(
        default=None,
        description="Short user-facing ETA text such as Arr, 3m, or Not In Operation.",
    )
    minutes: int | None = Field(
        default=None,
        description="ETA in minutes when available.",
    )
    status: ArrivalStatus = Field(
        description=(
            "Normalized arrival status, for example ARRIVING, "
            "NO_ESTIMATE, or NOT_IN_OPERATION."
        ),
    )
    load: BusLoad | None = Field(default=None, description="Raw LTA crowd load code.")
    load_label: str | None = Field(
        default=None,
        description="Human-readable crowd load label.",
    )
    load_color: LoadColor | None = Field(
        default=None,
        description="Frontend-friendly load color token.",
    )
    wheelchair: bool = Field(
        default=False,
        description="Whether the incoming bus is wheelchair accessible.",
    )
    bus_type: BusType | None = Field(default=None, description="Raw LTA bus type code.")
    bus_type_label: str | None = Field(
        default=None,
        description="Human-readable bus type label.",
    )
    monitored: bool = Field(
        default=False,
        description="Whether LTA marks this bus as monitored.",
    )
    estimated_arrival: datetime | None = Field(
        default=None,
        description="Estimated arrival timestamp in ISO 8601 format.",
    )


class BusServiceArrival(BaseModel):
    service_no: str = Field(description="Bus service number.")
    operator: str | None = Field(default=None, description="LTA operator code.")
    is_favorite: bool = Field(
        default=False,
        description="Whether this bus stop and service pair is favorited by the current user.",
    )
    favorite_id: str | None = Field(
        default=None,
        description="Favorite item identifier when the service is favorited by the user.",
    )
    group_id: str | None = Field(
        default=None,
        description="Favorite group identifier when the service is favorited by the user.",
    )
    group_name: str | None = Field(
        default=None,
        description="Favorite group name when the service is favorited by the user.",
    )
    display_order: int | None = Field(
        default=None,
        description="Display order of the matching favorite item.",
    )
    arrivals: list[ArrivalItem]


class ArrivalsPayload(BaseModel):
    bus_stop_code: str = Field(description="5-digit bus stop code.")
    description: str | None = Field(
        default=None,
        description="Official LTA bus stop name.",
    )
    display_name: str | None = Field(
        default=None,
        description=(
            "User-facing bus stop name. Uses the current user's alias; "
            "user_device_id is required."
        ),
    )
    road_name: str | None = Field(default=None, description="Road name of the bus stop.")
    latitude: float | None = Field(default=None, description="Bus stop latitude.")
    longitude: float | None = Field(default=None, description="Bus stop longitude.")
    updated_at: datetime = Field(
        description="Timestamp when this arrival payload was produced.",
    )
    services: list[BusServiceArrival]


class BatchArrivalItemRequest(BaseModel):
    bus_stop_code: str = Field(
        min_length=5,
        max_length=5,
        description="5-digit bus stop code.",
    )
    service_no: str = Field(description="Bus service number to return for this stop.")


class BatchArrivalRequest(BaseModel):
    items: list[BatchArrivalItemRequest] = Field(
        min_length=1,
        max_length=50,
        description="Bus stop and service pairs to fetch in one request.",
    )


class BatchArrivalItem(BaseModel):
    bus_stop_code: str
    service_no: str
    status: str = Field(description="Item-level status such as OK, NOT_FOUND, or ERROR.")
    arrivals: list[ArrivalItem]
    error_code: str | None = Field(
        default=None,
        description="Optional item-level error code when status is not OK.",
    )


class BatchArrivalsPayload(BaseModel):
    updated_at: datetime
    items: list[BatchArrivalItem]
