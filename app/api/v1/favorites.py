from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_favorite_service
from app.schemas.common import ApiResponse, ErrorResponse, MetaResponse
from app.schemas.favorite import (
    FavoriteCreate,
    FavoriteCreatedPayload,
    FavoriteGroupCreate,
    FavoriteGroupListPayload,
    FavoriteGroupSummary,
    FavoriteGroupUpdate,
    FavoriteReorderRequest,
    FavoriteReorderResultItem,
    FavoriteReorderResultPayload,
)
from app.services.favorite_service import FavoriteService

router = APIRouter(prefix="/favorites", tags=["favorites"])
group_router = APIRouter(prefix="/favorite-groups", tags=["favorite-groups"])

NOT_FOUND_GROUP_RESPONSE = {
    "model": ErrorResponse,
    "description": "Favorite group does not exist.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "FAVORITE_GROUP_NOT_FOUND",
                    "message": "Favorite group does not exist.",
                    "request_id": "req_demo123456",
                }
            }
        }
    },
}

NOT_FOUND_FAVORITE_RESPONSE = {
    "model": ErrorResponse,
    "description": "Favorite does not exist.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "FAVORITE_NOT_FOUND",
                    "message": "Favorite does not exist.",
                    "request_id": "req_demo123456",
                }
            }
        }
    },
}

DUPLICATE_FAVORITE_RESPONSE = {
    "model": ErrorResponse,
    "description": "The same bus stop and service already exists in the group.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "FAVORITE_ALREADY_EXISTS",
                    "message": "This service is already in the selected favorite group.",
                    "request_id": "req_demo123456",
                }
            }
        }
    },
}


@group_router.get(
    "",
    response_model=ApiResponse[FavoriteGroupListPayload],
    summary="List favorite groups",
    responses={
        200: {
            "description": "Favorite groups for the current user.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "items": [
                                {
                                    "id": "7d5b7f8e-caa2-4d57-9f82-b0f6a65cb1cb",
                                    "name": "Home",
                                    "emoji": "H",
                                    "display_order": 0,
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
async def list_groups(
    user_device_id: str = Query(),
    service: FavoriteService = Depends(get_favorite_service),
) -> ApiResponse[FavoriteGroupListPayload]:
    groups = await service.list_groups(user_device_id)
    return ApiResponse(
        data=FavoriteGroupListPayload(
            items=[
                FavoriteGroupSummary(
                    id=group.id,
                    name=group.name,
                    emoji=group.emoji,
                    display_order=group.display_order,
                )
                for group in groups
            ]
        ),
        meta=MetaResponse(),
    )


@group_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[FavoriteGroupSummary],
    summary="Create a favorite group",
    responses={
        201: {
            "description": "Favorite group created.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "id": "7d5b7f8e-caa2-4d57-9f82-b0f6a65cb1cb",
                            "name": "Home",
                            "emoji": "H",
                            "display_order": 0,
                        },
                        "meta": {"request_id": None, "updated_at": None, "stale": False},
                    }
                }
            },
        }
    },
)
async def create_group(
    payload: FavoriteGroupCreate,
    service: FavoriteService = Depends(get_favorite_service),
) -> ApiResponse[FavoriteGroupSummary]:
    group = await service.create_group(payload)
    return ApiResponse(
        data=FavoriteGroupSummary(
            id=group.id,
            name=group.name,
            emoji=group.emoji,
            display_order=group.display_order,
        ),
        meta=MetaResponse(),
    )


@group_router.patch(
    "/{group_id}",
    response_model=ApiResponse[FavoriteGroupSummary],
    summary="Update a favorite group",
    responses={
        200: {
            "description": "Favorite group updated.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "id": "7d5b7f8e-caa2-4d57-9f82-b0f6a65cb1cb",
                            "name": "Work",
                            "emoji": "W",
                            "display_order": 2,
                        },
                        "meta": {"request_id": None, "updated_at": None, "stale": False},
                    }
                }
            },
        },
        404: NOT_FOUND_GROUP_RESPONSE,
    },
)
async def update_group(
    group_id: UUID,
    payload: FavoriteGroupUpdate,
    service: FavoriteService = Depends(get_favorite_service),
) -> ApiResponse[FavoriteGroupSummary]:
    group = await service.update_group(group_id, payload)
    return ApiResponse(
        data=FavoriteGroupSummary(
            id=group.id,
            name=group.name,
            emoji=group.emoji,
            display_order=group.display_order,
        ),
        meta=MetaResponse(),
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[FavoriteCreatedPayload],
    summary="Create a favorite bus service",
    description=(
        "Creates or reuses a station-based favorite card. "
        "If `group_id` is omitted, backend will automatically reuse the user's "
        "existing card for the same bus stop, or create a new card "
        "named after the current bus stop. "
        "If `group_id` points to a different bus stop, backend will ignore it "
        "and still use the current bus stop's card."
    ),
    responses={
        201: {
            "description": "Favorite created.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "id": "2f80f65a-cd0f-4af6-a4e4-2405511bd6df",
                            "favorite_id": "2f80f65a-cd0f-4af6-a4e4-2405511bd6df",
                            "group_id": "7d5b7f8e-caa2-4d57-9f82-b0f6a65cb1cb",
                            "group_name": "Opp Example Stop",
                            "bus_stop_code": "83139",
                            "service_no": "36",
                            "display_order": 0,
                            "created_group": True,
                            "already_exists": False,
                        },
                        "meta": {"request_id": None, "updated_at": None, "stale": False},
                    }
                }
            },
        },
        404: {
            "model": ErrorResponse,
            "description": "Related resource does not exist.",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_group": {
                            "summary": "Favorite group missing",
                            "value": {
                                "error": {
                                    "code": "FAVORITE_GROUP_NOT_FOUND",
                                    "message": "Favorite group does not exist for this user.",
                                    "request_id": "req_demo123456",
                                }
                            },
                        },
                        "missing_bus_stop": {
                            "summary": "Bus stop missing",
                            "value": {
                                "error": {
                                    "code": "BUS_STOP_NOT_FOUND",
                                    "message": "Bus stop does not exist.",
                                    "request_id": "req_demo123456",
                                }
                            },
                        },
                    }
                }
            },
        },
        409: DUPLICATE_FAVORITE_RESPONSE,
    },
)
async def create_favorite(
    payload: FavoriteCreate,
    service: FavoriteService = Depends(get_favorite_service),
) -> ApiResponse[FavoriteCreatedPayload]:
    result = await service.create_favorite(payload)
    favorite = result.favorite
    group = await service.get_group(favorite.group_id)
    return ApiResponse(
        data=FavoriteCreatedPayload(
            id=favorite.id,
            favorite_id=favorite.id,
            group_id=favorite.group_id,
            group_name=group.name if group is not None else "",
            bus_stop_code=favorite.bus_stop_code,
            service_no=favorite.service_no,
            display_order=favorite.display_order,
            created_group=result.created_group,
            already_exists=result.already_exists,
        ),
        meta=MetaResponse(),
    )


@router.patch(
    "/reorder",
    response_model=ApiResponse[FavoriteReorderResultPayload],
    summary="Reorder favorite items",
    responses={
        200: {
            "description": "Favorites reordered.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "items": [
                                {
                                    "favorite_id": "2f80f65a-cd0f-4af6-a4e4-2405511bd6df",
                                    "display_order": 0,
                                }
                            ]
                        },
                        "meta": {"request_id": None, "updated_at": None, "stale": False},
                    }
                }
            },
        },
        404: NOT_FOUND_FAVORITE_RESPONSE,
    },
)
async def reorder_favorites(
    payload: FavoriteReorderRequest,
    service: FavoriteService = Depends(get_favorite_service),
) -> ApiResponse[FavoriteReorderResultPayload]:
    items = await service.reorder_favorites(payload)
    return ApiResponse(
        data=FavoriteReorderResultPayload(
            items=[
                FavoriteReorderResultItem(
                    favorite_id=item.id,
                    display_order=item.display_order,
                )
                for item in items
            ]
        ),
        meta=MetaResponse(),
    )


@group_router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a favorite group",
    responses={404: NOT_FOUND_GROUP_RESPONSE},
)
async def delete_group(
    group_id: UUID,
    user_device_id: str = Query(),
    service: FavoriteService = Depends(get_favorite_service),
) -> None:
    await service.delete_group(group_id, user_device_id)


@router.delete(
    "/{favorite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a favorite item",
    responses={404: NOT_FOUND_FAVORITE_RESPONSE},
)
async def delete_favorite(
    favorite_id: UUID,
    user_device_id: str = Query(),
    service: FavoriteService = Depends(get_favorite_service),
) -> None:
    await service.delete_favorite(favorite_id, user_device_id)
