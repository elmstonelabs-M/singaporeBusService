from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    user_device_id: str | None = Field(
        default=None,
        description="Optional stable client-side device identifier.",
    )
    contact_email: str | None = Field(
        default=None,
        description="Optional reply-to email from the user.",
    )
    category: str | None = Field(default=None, description="Optional feedback category.")
    subject: str | None = Field(default=None, description="Optional feedback subject.")
    message: str = Field(min_length=1, description="Feedback message body.")
    app_version: str | None = Field(default=None, description="Frontend app version.")
    device_info: str | None = Field(default=None, description="Optional device/environment info.")


class FeedbackView(BaseModel):
    id: UUID
    user_device_id: str | None = None
    contact_email: str | None = None
    category: str | None = None
    subject: str | None = None
    message: str
    app_version: str | None = None
    device_info: str | None = None
    email_status: str
    created_at: datetime


class FeedbackCreatePayload(BaseModel):
    feedback: FeedbackView
