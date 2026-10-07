from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.constants import CertificateStatus
from app.utils.time_utils import utc_now


class Certificate(Base):
    """One certificate for one recipient of a job."""

    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    recipient_name: Mapped[str] = mapped_column(String(100))
    recipient_email: Mapped[str] = mapped_column(String(254))
    status: Mapped[str] = mapped_column(
        String(20), default=CertificateStatus.PENDING.value, index=True
    )
    # Path RELATIVE to the certificates directory (never exposed through the API).
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    job: Mapped["Job"] = relationship(back_populates="certificates")  # noqa: F821

    @property
    def certificate_code(self) -> str:
        """Human-friendly unique ID, derived from the primary key: CERT-000001."""
        return f"CERT-{self.id:06d}"
