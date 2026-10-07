"""Shared constants and enums."""
from enum import StrEnum

API_V1_PREFIX = "/api/v1"

# Input size limits (keeps requests reasonable and PDFs readable).
MAX_RECIPIENTS_PER_JOB = 1000
MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 254
MAX_EVENT_NAME_LENGTH = 150
MAX_ORGANIZATION_NAME_LENGTH = 150
MAX_IDEMPOTENCY_KEY_LENGTH = 128
MAX_ERROR_MESSAGE_LENGTH = 500


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"


class CertificateStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
