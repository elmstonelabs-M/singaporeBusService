from fastapi import APIRouter, Depends, Query

from app.api.deps import get_home_service
from app.schemas.common import ApiResponse, MetaResponse
from app.schemas.home import HomePayload
from app.services.home_service import HomeService

router = APIRouter(prefix="/home", tags=["home"])


@router.get(
    "",
    response_model=ApiResponse[HomePayload],
    summary="Get home screen payload",
    description=(
        "Returns the aggregated home payload for a user, including favorite groups "
        "with arrival snippets and nearby bus stops."
    ),
    responses={
        200: {
            "description": "Home payload for the current user.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "location_label": "Office Stop, Singapore",
                            "updated_at": "2026-05-20T14:30:00+08:00",
                            "favorite_groups": [
                                {
                                    "id": "7d5b7f8e-caa2-4d57-9f82-b0f6a65cb1cb",
                                    "group_id": "7d5b7f8e-caa2-4d57-9f82-b0f6a65cb1cb",
                                    "name": "Home",
                                    "emoji": "H",
                                    "display_order": 0,
                                    "bus_stop_code": "83139",
                                    "latitude": 1.3001,
                                    "longitude": 103.9001,
                                    "items": [
                                        {
                                            "id": "2f80f65a-cd0f-4af6-a4e4-2405511bd6df",
                                            "favorite_id": "2f80f65a-cd0f-4af6-a4e4-2405511bd6df",
                                            "group_id": "7d5b7f8e-caa2-4d57-9f82-b0f6a65cb1cb",
                                            "group_name": "Home",
                                            "bus_stop_code": "83139",
                                            "description": "Opp Example Stop",
                                            "display_name": "Office Stop",
                                            "road_name": "Marine Parade Rd",
                                            "service_no": "36",
                                            "is_favorite": True,
                                            "display_order": 0,
                                            "arrivals": [
                                                {
                                                    "sequence": 1,
                                                    "display": "3m",
                                                    "minutes": 3,
                                                    "status": "ARRIVING",
                                                    "load": "SEA",
                                                    "load_label": "Seats Available",
                                                    "load_color": "green",
                                                    "wheelchair": True,
                                                    "bus_type": "DD",
                                                    "bus_type_label": "Double Deck",
                                                    "monitored": True,
                                                    "estimated_arrival": (
                                                        "2026-05-20T14:33:00+08:00"
                                                    ),
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                            "nearby_bus_stops": [
                                {
                                    "bus_stop_code": "83139",
                                    "description": "Opp Example Stop",
                                    "display_name": "Office Stop",
                                    "road_name": "Marine Parade Rd",
                                    "latitude": 1.3001,
                                    "longitude": 103.9001,
                                    "distance_m": 110,
                                    "distance_label": "110m",
                                    "has_arrival_data": True,
                                }
                            ],
                        },
                        "meta": {
                            "request_id": None,
                            "updated_at": "2026-05-20T14:30:00+08:00",
                            "stale": False,
                        },
                    }
                }
            },
        }
    },
)
async def get_home(
    user_device_id: str = Query(),
    lat: float | None = Query(default=None),
    lng: float | None = Query(default=None),
    service: HomeService = Depends(get_home_service),
) -> ApiResponse[HomePayload]:
    payload = await service.get_home(user_device_id=user_device_id, lat=lat, lng=lng)
    return ApiResponse(data=payload, meta=MetaResponse(updated_at=payload.updated_at))
