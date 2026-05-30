from fastapi import APIRouter, Depends, Query

from app.api.deps import get_arrival_service
from app.schemas.arrival import BatchArrivalRequest, BatchArrivalsPayload
from app.schemas.common import ApiResponse
from app.services.arrival_service import ArrivalService

router = APIRouter(prefix="/arrivals", tags=["arrivals"])


@router.post(
    "/batch",
    response_model=ApiResponse[BatchArrivalsPayload],
    summary="Get real-time arrivals for multiple bus stop and service pairs",
    description=(
        "Returns arrivals for multiple bus stop/service pairs. The service groups "
        "requests by bus stop and uses station-level cache first, so multiple "
        "services at the same stop do not trigger repeated LTA requests."
    ),
)
async def get_batch_arrivals(
    payload: BatchArrivalRequest,
    user_device_id: str | None = Query(default=None),
    service: ArrivalService = Depends(get_arrival_service),
) -> ApiResponse[BatchArrivalsPayload]:
    result = await service.get_batch_arrivals(
        [item.model_dump() for item in payload.items],
        user_device_id=user_device_id,
    )
    return ApiResponse.model_validate(result)
