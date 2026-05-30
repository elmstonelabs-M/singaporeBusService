from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackCreate, FeedbackView
from app.services.feedback_email_service import FeedbackEmailService


class FeedbackService:
    def __init__(self, db: AsyncSession, email_service: FeedbackEmailService) -> None:
        self.db = db
        self.email_service = email_service

    async def create_feedback(self, payload: FeedbackCreate) -> Feedback:
        feedback = Feedback(
            user_device_id=payload.user_device_id,
            contact_email=str(payload.contact_email) if payload.contact_email else None,
            category=payload.category,
            subject=payload.subject,
            message=payload.message,
            app_version=payload.app_version,
            device_info=payload.device_info,
            email_status="pending",
        )
        self.db.add(feedback)
        await self.db.commit()
        await self.db.refresh(feedback)

        feedback_view = FeedbackView.model_validate(feedback, from_attributes=True)
        try:
            await self.email_service.send_feedback(feedback_view)
            feedback.email_status = "sent"
            feedback.email_error = None
        except Exception as exc:
            feedback.email_status = "failed"
            feedback.email_error = str(exc)
        await self.db.commit()
        await self.db.refresh(feedback)
        return feedback
