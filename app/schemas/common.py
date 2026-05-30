from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MetaResponse(BaseModel):
    request_id: str | None = Field(
        default=None,
        description="Request identifier for tracing and error correlation.",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Timestamp for the payload when provided by the endpoint.",
    )
    stale: bool = Field(
        default=False,
        description="Whether the data came from stale fallback cache.",
    )


class ApiResponse(BaseModel, Generic[T]):
    data: T
    meta: MetaResponse = Field(default_factory=MetaResponse)


class ErrorBody(BaseModel):
    code: str = Field(description="Application-level error code.")
    message: str = Field(description="Human-readable error message.")
    request_id: str | None = Field(
        default=None,
        description="Request identifier for correlating logs and client errors.",
    )


class ErrorResponse(BaseModel):
    error: ErrorBody
