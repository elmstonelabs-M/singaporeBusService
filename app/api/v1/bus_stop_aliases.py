from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_bus_stop_alias_service
from app.schemas.bus_stop import BusStopAliasListPayload, BusStopAliasUpsert, BusStopAliasView
from app.schemas.common import ApiResponse, MetaResponse
from app.services.bus_stop_alias_service import BusStopAliasService

router = APIRouter(prefix="/bus-stop-aliases", tags=["bus-stop-aliases"])


@router.get(
    "",
    response_model=ApiResponse[BusStopAliasListPayload],
    summary="List bus stop aliases for a user",
)
async def list_aliases(
    user_device_id: str = Query(),
    service: BusStopAliasService = Depends(get_bus_stop_alias_service),
) -> ApiResponse[BusStopAliasListPayload]:
    aliases = await service.list_aliases(user_device_id)
    return ApiResponse(
        data=BusStopAliasListPayload(
            items=[
                BusStopAliasView(
                    bus_stop_code=item.bus_stop_code,
                    alias=item.alias,
                    updated_at=item.updated_at,
                )
                for item in aliases
            ]
        ),
        meta=MetaResponse(),
    )


@router.put(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[BusStopAliasView],
    summary="Create or update a bus stop alias",
)
async def upsert_alias(
    payload: BusStopAliasUpsert,
    service: BusStopAliasService = Depends(get_bus_stop_alias_service),
) -> ApiResponse[BusStopAliasView]:
    alias = await service.upsert_alias(payload)
    return ApiResponse(
        data=BusStopAliasView(
            bus_stop_code=alias.bus_stop_code,
            alias=alias.alias,
            updated_at=alias.updated_at,
        ),
        meta=MetaResponse(),
    )


@router.delete("/{bus_stop_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alias(
    bus_stop_code: str,
    user_device_id: str = Query(),
    service: BusStopAliasService = Depends(get_bus_stop_alias_service),
) -> None:
    await service.delete_alias(user_device_id, bus_stop_code)
