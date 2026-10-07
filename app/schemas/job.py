from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.job import Job
from app.utils.constants import (
    MAX_EMAIL_LENGTH,
    MAX_EVENT_NAME_LENGTH,
    MAX_NAME_LENGTH,
    MAX_ORGANIZATION_NAME_LENGTH,
    MAX_RECIPIENTS_PER_JOB,
    JobStatus,
)


def _strip_and_require(value: str) -> str:
    """Trim whitespace; reject strings that are empty after trimming."""
    value = value.strip()
    if not value:
        raise ValueError("must not be empty or only whitespace")
    return value


class RecipientIn(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, examples=["Nivetha L G"])
    email: EmailStr = Field(max_length=MAX_EMAIL_LENGTH, examples=["nivetha@example.com"])

    _clean_name = field_validator("name")(_strip_and_require)


class JobCreateRequest(BaseModel):
    event_name: str = Field(
        min_length=1, max_length=MAX_EVENT_NAME_LENGTH, examples=["AI Workshop 2026"]
    )
    event_date: date = Field(description="ISO format: YYYY-MM-DD", examples=["2026-10-07"])
    organization_name: str = Field(
        min_length=1, max_length=MAX_ORGANIZATION_NAME_LENGTH, examples=["ABC Organization"]
    )
    recipients: Annotated[
        list[RecipientIn], Field(min_length=1, max_length=MAX_RECIPIENTS_PER_JOB)
    ]

    _clean_event_name = field_validator("event_name")(_strip_and_require)
    _clean_organization = field_validator("organization_name")(_strip_and_require)


class JobCreatedResponse(BaseModel):
    job_id: int
    status: JobStatus
    total: int
    message: str


class JobStatusResponse(BaseModel):
    job_id: int
    status: JobStatus
    total: int
    successful: int
    failed: int
    progress_percentage: int = Field(ge=0, le=100)
    created_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def from_model(cls, job: Job) -> "JobStatusResponse":
        return cls(
            job_id=job.id,
            status=job.status,
            total=job.total_count,
            successful=job.successful_count,
            failed=job.failed_count,
            progress_percentage=job.progress_percentage,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )
