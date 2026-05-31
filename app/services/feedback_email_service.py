import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings
from app.core.errors import ExternalServiceError
from app.schemas.feedback import FeedbackView

settings = get_settings()


class FeedbackEmailService:
    async def send_feedback(self, feedback: FeedbackView) -> None:
        if not settings.smtp_host or not settings.smtp_from_email:
            raise ExternalServiceError(
                "FEEDBACK_EMAIL_NOT_CONFIGURED",
                "Feedback email delivery is not configured.",
            )
        await asyncio.to_thread(self._send_feedback_sync, feedback)

    def _send_feedback_sync(self, feedback: FeedbackView) -> None:
        message = EmailMessage()
        message["Subject"] = feedback.subject or f"Singapore Bus App Feedback {feedback.id}"
        message["From"] = settings.smtp_from_email
        message["To"] = settings.feedback_to_email
        if feedback.contact_email:
            message["Reply-To"] = feedback.contact_email

        message.set_content(
            "\n".join(
                [
                    f"Feedback ID: {feedback.id}",
                    f"Created At: {feedback.created_at.isoformat()}",
                    f"User Device ID: {feedback.user_device_id or ''}",
                    f"Client IP: {feedback.client_ip or ''}",
                    f"Contact Email: {feedback.contact_email or ''}",
                    f"Category: {feedback.category or ''}",
                    f"Subject: {feedback.subject or ''}",
                    f"App Version: {feedback.app_version or ''}",
                    f"Device Info: {feedback.device_info or ''}",
                    "",
                    "Message:",
                    feedback.message,
                ]
            )
        )

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(message)
        except OSError as exc:
            raise ExternalServiceError(
                "FEEDBACK_EMAIL_SEND_FAILED",
                "Failed to send feedback email.",
            ) from exc
