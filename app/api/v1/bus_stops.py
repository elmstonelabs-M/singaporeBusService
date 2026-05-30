from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_arrival_service, get_bus_stop_service
from app.schemas.arrival import ArrivalsPayload
from app.schemas.bus_stop import BusStopListPayload
from app.schemas.common import ApiResponse, ErrorResponse, MetaResponse
from app.services.arrival_service import ArrivalService
from app.services.bus_stop_service import BusStopService

router = APIRouter(prefix="/bus-stops", tags=["bus-stops"])


@router.get(
    "/{bus_stop_code}/arrivals",
    response_model=ApiResponse[ArrivalsPayload],
    summary="Get real-time arrivals for a bus stop",
    description=(
        "Returns station metadata plus real-time arrivals. "
        "`user_device_id` is optional; when provided, the response can include "
        "the user's station alias in `display_name` and user-specific "
        "`is_favorite` flags."
    ),
    responses={
        200: {
            "description": "Real-time arrivals for the requested bus stop.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "bus_stop_code": "83139",
                            "description": "Opp Example Stop",
                            "display_name": "Office Stop",
                            "road_name": "Marine Parade Rd",
                            "latitude": 1.3001,
                            "longitude": 103.9001,
                            "updated_at": "2026-05-20T14:30:00+08:00",
                            "services": [
                                {
                                    "service_no": "36",
                                    "operator": "SBST",
                                    "is_favorite": True,
                                    "favorite_id": "2f80f65a-cd0f-4af6-a4e4-2405511bd6df",
                                    "group_id": "7d5b7f8e-caa2-4d57-9f82-b0f6a65cb1cb",
                                    "group_name": "Home",
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
                        },
                        "meta": {
                            "request_id": None,
                            "updated_at": "2026-05-20T14:30:00+08:00",
                            "stale": False,
                        },
                    }
                }
            },
        },
        422: {
            "model": ErrorResponse,
            "description": "Invalid bus stop code.",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVALID_BUS_STOP_CODE",
                            "message": "Bus stop code must be a 5-digit number.",
                            "request_id": "req_demo123456",
                        }
                    }
                }
            },
        },
        503: {
            "model": ErrorResponse,
            "description": "LTA request failed and no fallback cache is available.",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "LTA_REQUEST_FAILED",
                            "message": "Failed to fetch arrival data.",
                            "request_id": "req_demo123456",
                        }
                    }
                }
            },
        },
    },
)
async def get_arrivals(
    bus_stop_code: str,
    service_no: str | None = Query(default=None),
    user_device_id: str | None = Query(default=None),
    service: ArrivalService = Depends(get_arrival_service),
) -> ApiResponse[ArrivalsPayload]:
    payload = await service.get_arrivals(
        bus_stop_code,
        service_no=service_no,
        user_device_id=user_device_id,
    )
    return ApiResponse.model_validate(payload)


@router.get(
    "/nearby",
    response_model=ApiResponse[BusStopListPayload],
    summary="Find nearby bus stops",
    description=(
        "Returns nearby bus stops ordered by distance. "
        "`user_device_id` is optional so each item's `display_name` can respect "
        "the user's alias when available."
    ),
    responses={
        200: {
            "description": "Nearby bus stops ordered by distance.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "items": [
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
                            ]
                        },
                        "meta": {"request_id": None, "updated_at": None, "stale": False},
                    }
                }
            },
        }
    },
)
async def nearby_bus_stops(
    lat: Annotated[float, Query()],
    lng: Annotated[float, Query()],
    radius: int = Query(default=800, ge=1, le=3000),
    limit: int = Query(default=20, ge=1, le=100),
    user_device_id: str | None = Query(default=None),
    service: BusStopService = Depends(get_bus_stop_service),
) -> ApiResponse[BusStopListPayload]:
    items = await service.nearby(
        lat=lat,
        lng=lng,
        radius=radius,
        limit=limit,
        user_device_id=user_device_id,
    )
    return ApiResponse(
        data=BusStopListPayload(items=items),
        meta=MetaResponse(),
    )


@router.get(
    "/search",
    response_model=ApiResponse[BusStopListPayload],
    summary="Search bus stops",
    description=(
        "Searches bus stops by code, description, road name, or indexed search text. "
        "`user_device_id` is optional so each item's `display_name` can respect "
        "the user's alias when available."
    ),
    responses={
        200: {
            "description": "Bus stop search results.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "items": [
                                {
                                    "bus_stop_code": "83139",
                                    "description": "Opp Example Stop",
                                    "display_name": "Office Stop",
                                    "road_name": "Marine Parade Rd",
                                    "latitude": 1.3001,
                                    "longitude": 103.9001,
                                    "distance_m": None,
                                    "distance_label": None,
                                    "has_arrival_data": False,
                                }
                            ]
                        },
                        "meta": {"request_id": None, "updated_at": None, "stale": False},
                    }
                }
            },
        }
    },
)
async def search_bus_stops(
    q: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    user_device_id: str | None = Query(default=None),
    service: BusStopService = Depends(get_bus_stop_service),
) -> ApiResponse[BusStopListPayload]:
    items = await service.search(query=q, limit=limit, user_device_id=user_device_id)
    return ApiResponse(
        data=BusStopListPayload(items=items),
        meta=MetaResponse(),
    )
