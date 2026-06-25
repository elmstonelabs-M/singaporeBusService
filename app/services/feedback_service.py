from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import RateLimitError
from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackCreate, FeedbackView
from app.services.feedback_email_service import FeedbackEmailService
from app.utils.time_utils import singapore_now

settings = get_settings()


class FeedbackService:
    def __init__(self, db: AsyncSession, email_service: FeedbackEmailService) -> None:
        self.db = db
        self.email_service = email_service

    async def create_feedback(self, payload: FeedbackCreate, client_ip: str) -> Feedback:
        await self._ensure_daily_limit(
            client_ip=client_ip,
            client_id=payload.user_device_id,
        )
        feedback = Feedback(
            user_device_id=payload.user_device_id,
            client_ip=client_ip,
            contact_email=str(payload.contact_email) if payload.contact_email else None,
            category=payload.category,
            subject=payload.subject,
            message=payload.message,
            app_version=payload.app_version,
            device_info=payload.device_info,
            email_status="pending",
            created_at=singapore_now(),
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

    async def _ensure_daily_limit(
        self,
        client_ip: str,
        client_id: str | None,
    ) -> None:
        now = singapore_now()
        start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
        next_day = start + timedelta(days=1)

        if client_id:
            client_id_result = await self.db.execute(
                select(func.count(Feedback.id)).where(
                    Feedback.user_device_id == client_id,
                    Feedback.created_at >= start,
                    Feedback.created_at < next_day,
                )
            )
            client_id_count = client_id_result.scalar_one()
            if client_id_count >= settings.feedback_daily_limit_per_client_id:
                raise RateLimitError(
                    "FEEDBACK_CLIENT_DAILY_LIMIT_EXCEEDED",
                    "This device has reached today's feedback limit. Please try again tomorrow.",
                )

        ip_result = await self.db.execute(
            select(func.count(Feedback.id)).where(
                Feedback.client_ip == client_ip,
                Feedback.created_at >= start,
                Feedback.created_at < next_day,
            )
        )
        ip_count = ip_result.scalar_one()
        if ip_count >= settings.feedback_daily_limit_per_ip:
            raise RateLimitError(
                "FEEDBACK_IP_DAILY_LIMIT_EXCEEDED",
                "This network has reached today's feedback limit. Please try again tomorrow.",
            )
