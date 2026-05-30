from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field

from app.schemas.arrival import ArrivalItem

if TYPE_CHECKING:
    from app.models.favorite import FavoriteItem


def _empty_string_to_none(value: object) -> object:
    if value == "":
        return None
    return value


class FavoriteGroupCreate(BaseModel):
    user_device_id: str = Field(description="Client-side stable user device identifier.")
    name: str = Field(description="Favorite group name.")
    emoji: str | None = Field(default=None, description="Optional emoji label for the group.")
    display_order: int = Field(default=0, description="Sort order within the user's groups.")


class FavoriteCreate(BaseModel):
    user_device_id: str = Field(description="Client-side stable user device identifier.")
    group_id: Annotated[UUID | None, BeforeValidator(_empty_string_to_none)] = Field(
        default=None,
        description=(
            "Target favorite group identifier. "
            "If omitted, backend will auto-reuse the current user's existing card for the "
            "same bus stop or create a new card named after the current bus stop. "
            "If provided for a different bus stop, backend will ignore it and still use "
            "the current bus stop's card semantics."
        ),
    )
    bus_stop_code: str = Field(description="5-digit bus stop code.")
    service_no: str = Field(description="Bus service number.")
    display_order: int = Field(default=0, description="Sort order within the group.")


class FavoriteGroupUpdate(BaseModel):
    user_device_id: str = Field(description="Client-side stable user device identifier.")
    name: str | None = Field(default=None, description="Updated favorite group name.")
    emoji: str | None = Field(default=None, description="Updated emoji label.")
    display_order: int | None = Field(default=None, description="Updated display order.")


class FavoriteReorderItem(BaseModel):
    favorite_id: UUID = Field(description="Favorite item identifier.")
    display_order: int = Field(description="New display order for this favorite.")


class FavoriteReorderRequest(BaseModel):
    user_device_id: str = Field(description="Client-side stable user device identifier.")
    items: list[FavoriteReorderItem]


class FavoriteItemView(BaseModel):
    id: UUID
    favorite_id: UUID
    group_id: UUID
    group_name: str
    bus_stop_code: str
    description: str
    display_name: str
    road_name: str
    service_no: str
    is_favorite: bool = True
    display_order: int
    arrivals: list[ArrivalItem] = Field(default_factory=list)


class FavoriteGroupView(BaseModel):
    id: UUID
    group_id: UUID
    name: str
    emoji: str | None = None
    display_order: int
    bus_stop_code: str | None = Field(
        default=None,
        description="Primary bus stop code for this station-based favorite card.",
    )
    latitude: float | None = Field(
        default=None,
        description="Latitude of the station represented by this favorite card.",
    )
    longitude: float | None = Field(
        default=None,
        description="Longitude of the station represented by this favorite card.",
    )
    items: list[FavoriteItemView]


class FavoriteGroupSummary(BaseModel):
    id: UUID
    name: str
    emoji: str | None = None
    display_order: int


class FavoriteGroupListPayload(BaseModel):
    items: list[FavoriteGroupSummary]


class FavoriteCreatedPayload(BaseModel):
    id: UUID
    favorite_id: UUID
    group_id: UUID
    group_name: str
    bus_stop_code: str
    service_no: str
    display_order: int
    created_group: bool = False
    already_exists: bool = False


@dataclass(slots=True)
class FavoriteCreatedResult:
    favorite: "FavoriteItem"
    created_group: bool = False
    already_exists: bool = False


class ReorderResultPayload(BaseModel):
    updated: int


class FavoriteReorderResultItem(BaseModel):
    favorite_id: UUID
    display_order: int


class FavoriteReorderResultPayload(BaseModel):
    items: list[FavoriteReorderResultItem]
