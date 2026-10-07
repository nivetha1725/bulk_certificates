"""Background processing of a job.

Key idea: every certificate is processed inside its OWN try/except, so one
failure is recorded and the loop simply moves on to the next recipient.
"""
import logging
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionFactory
from app.models.certificate import Certificate
from app.models.job import Job
from app.services.certificate_generator import CertificateData
from app.services.file_storage import build_relative_path
from app.utils.constants import (
    MAX_ERROR_MESSAGE_LENGTH,
    CertificateStatus,
    JobStatus,
)
from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)

# (certificate data, absolute output path) -> None. Raises on failure.
CertificateGenerator = Callable[[CertificateData, Path], None]


def process_job(
    job_id: int,
    session_factory: SessionFactory,
    generator: CertificateGenerator,
    output_dir: Path,
) -> None:
    """Entry point used by FastAPI BackgroundTasks.

    Opens its own session: the request-scoped session is already closed
    by the time a background task runs.
    """
    db = session_factory()
    try:
        _run_job(db, job_id, generator, output_dir)
    except Exception:
        logger.exception("Unexpected error while processing job %s", job_id)
        _mark_job_failed(db, job_id)
    finally:
        db.close()


def _run_job(db: Session, job_id: int, generator: CertificateGenerator, output_dir: Path) -> None:
    job = db.get(Job, job_id)
    if job is None:
        logger.error("Job %s not found; nothing to process", job_id)
        return

    job.status = JobStatus.PROCESSING.value
    db.commit()

    certificate_ids = list(
        db.scalars(select(Certificate.id).where(Certificate.job_id == job_id).order_by(Certificate.id))
    )
    for certificate_id in certificate_ids:
        _process_certificate(db, job, certificate_id, generator, output_dir)

    _finalize_job(db, job)


def _process_certificate(
    db: Session,
    job: Job,
    certificate_id: int,
    generator: CertificateGenerator,
    output_dir: Path,
) -> None:
    """Generate one certificate. Never raises: failures are stored in the DB."""
    certificate = db.get(Certificate, certificate_id)
    try:
        certificate.status = CertificateStatus.PROCESSING.value
        db.commit()

        relative_path = build_relative_path(job.id, certificate.certificate_code)
        data = CertificateData(
            certificate_code=certificate.certificate_code,
            recipient_name=certificate.recipient_name,
            event_name=job.event_name,
            event_date=job.event_date,
            organization_name=job.organization_name,
        )
        generator(data, output_dir / relative_path)

        certificate.status = CertificateStatus.SUCCESS.value
        certificate.file_path = relative_path.as_posix()
        certificate.completed_at = utc_now()
        job.successful_count += 1
        db.commit()
    except Exception as exc:
        logger.exception("Certificate %s failed", certificate_id)
        _record_failure(db, job, certificate_id, exc, output_dir)


def _record_failure(
    db: Session, job: Job, certificate_id: int, exc: Exception, output_dir: Path
) -> None:
    try:
        db.rollback()  # discard any half-finished changes from the failed attempt
        certificate = db.get(Certificate, certificate_id)
        certificate.status = CertificateStatus.FAILED.value
        certificate.error_message = _safe_error_message(exc, output_dir)
        certificate.completed_at = utc_now()
        job.failed_count += 1
        db.commit()
    except Exception:
        # Even recording the failure failed (e.g. DB problem). Log and keep going.
        logger.exception("Could not record failure for certificate %s", certificate_id)
        db.rollback()


def _safe_error_message(exc: Exception, output_dir: Path) -> str:
    """Short, useful message that does not reveal server file paths."""
    message = f"{type(exc).__name__}: {exc}".replace(str(output_dir), "<storage>")
    return message[:MAX_ERROR_MESSAGE_LENGTH]


def _finalize_job(db: Session, job: Job) -> None:
    if job.failed_count == 0:
        job.status = JobStatus.COMPLETED.value
    elif job.successful_count == 0:
        job.status = JobStatus.FAILED.value
    else:
        job.status = JobStatus.PARTIALLY_COMPLETED.value
    job.completed_at = utc_now()
    db.commit()
    logger.info(
        "Job %s finished: status=%s successful=%s failed=%s",
        job.id, job.status, job.successful_count, job.failed_count,
    )


def _mark_job_failed(db: Session, job_id: int) -> None:
    """Last resort if the processor itself crashes, so the job is not stuck."""
    try:
        db.rollback()
        job = db.get(Job, job_id)
        if job is not None:
            job.status = JobStatus.FAILED.value
            job.completed_at = utc_now()
            db.commit()
    except Exception:
        logger.exception("Could not mark job %s as failed", job_id)
