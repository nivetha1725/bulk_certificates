from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.certificate import Certificate
from app.utils.constants import API_V1_PREFIX, CertificateStatus


def build_download_url(certificate_id: int) -> str:
    return f"{API_V1_PREFIX}/certificates/{certificate_id}"


class CertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    certificate_id: int = Field(examples=[1])
    certificate_code: str = Field(examples=["CERT-000001"])
    recipient_name: str
    recipient_email: str
    status: CertificateStatus
    error_message: str | None = None
    download_url: str | None = Field(
        default=None, description="Only present when generation succeeded."
    )
    created_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def from_model(cls, certificate: Certificate) -> "CertificateResponse":
        is_success = certificate.status == CertificateStatus.SUCCESS
        return cls(
            certificate_id=certificate.id,
            certificate_code=certificate.certificate_code,
            recipient_name=certificate.recipient_name,
            recipient_email=certificate.recipient_email,
            status=certificate.status,
            error_message=certificate.error_message,
            download_url=build_download_url(certificate.id) if is_success else None,
            created_at=certificate.created_at,
            completed_at=certificate.completed_at,
        )


class CertificateListResponse(BaseModel):
    job_id: int
    total: int = Field(description="Number of certificates returned.")
    certificates: list[CertificateResponse]
