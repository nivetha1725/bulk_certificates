from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.constants import JobStatus
from app.utils.time_utils import utc_now


class Job(Base):
    """One bulk generation request. Owns many Certificates."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_name: Mapped[str] = mapped_column(String(150))
    event_date: Mapped[date] = mapped_column(Date)
    organization_name: Mapped[str] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.QUEUED.value, index=True)
    total_count: Mapped[int] = mapped_column(Integer)
    successful_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    # Optional client-supplied key used to avoid creating duplicate jobs.
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    certificates: Mapped[list["Certificate"]] = relationship(  # noqa: F821
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="Certificate.id",
    )

    @property
    def progress_percentage(self) -> int:
        """(successful + failed) / total, as a whole percentage."""
        if self.total_count == 0:
            return 0
        processed = self.successful_count + self.failed_count
        return min(100, processed * 100 // self.total_count)
