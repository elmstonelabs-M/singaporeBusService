from fastapi import APIRouter, Depends, status

from app.api.deps import get_feedback_service
from app.schemas.common import ApiResponse, MetaResponse
from app.schemas.feedback import FeedbackCreate, FeedbackCreatePayload, FeedbackView
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[FeedbackCreatePayload],
    summary="Submit user feedback",
    description=(
        "Stores feedback in the backend database and attempts to forward it to "
        "the configured feedback email recipient."
    ),
    responses={
        201: {
            "description": "Feedback stored successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "feedback": {
                                "id": "2f80f65a-cd0f-4af6-a4e4-2405511bd6df",
                                "user_device_id": "device-demo",
                                "contact_email": "user@example.com",
                                "category": "bug",
                                "subject": "Arrival list issue",
                                "message": "Favorite card did not refresh.",
                                "app_version": "1.0.0",
                                "device_info": "Pixel 8 / Android 15",
                                "email_status": "sent",
                                "created_at": "2026-05-21T12:00:00+08:00",
                            }
                        },
                        "meta": {
                            "request_id": None,
                            "updated_at": "2026-05-21T12:00:00+08:00",
                            "stale": False,
                        },
                    }
                }
            },
        }
    },
)
async def create_feedback(
    payload: FeedbackCreate,
    service: FeedbackService = Depends(get_feedback_service),
) -> ApiResponse[FeedbackCreatePayload]:
    feedback = await service.create_feedback(payload)
    view = FeedbackView.model_validate(feedback, from_attributes=True)
    return ApiResponse(
        data=FeedbackCreatePayload(feedback=view),
        meta=MetaResponse(updated_at=view.created_at),
    )
