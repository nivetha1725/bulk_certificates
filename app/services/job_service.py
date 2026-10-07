"""Database operations for jobs (kept out of the route functions)."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import CertificateNotFoundError, JobNotFoundError
from app.models.certificate import Certificate
from app.models.job import Job
from app.schemas.job import JobCreateRequest
from app.utils.constants import CertificateStatus, JobStatus


def get_job(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise JobNotFoundError(job_id)
    return job


def get_certificate(db: Session, certificate_id: int) -> Certificate:
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise CertificateNotFoundError(certificate_id)
    return certificate


def find_job_by_idempotency_key(db: Session, key: str) -> Job | None:
    return db.scalar(select(Job).where(Job.idempotency_key == key))


def create_job(
    db: Session, payload: JobCreateRequest, idempotency_key: str | None
) -> tuple[Job, bool]:
    """Create a job and its PENDING certificates in ONE transaction.

    Returns (job, created). If the same idempotency key was used before, the
    existing job is returned with created=False and nothing new is stored.
    """
    if idempotency_key:
        existing = find_job_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return existing, False

    job = Job(
        event_name=payload.event_name,
        event_date=payload.event_date,
        organization_name=payload.organization_name,
        status=JobStatus.QUEUED.value,
        total_count=len(payload.recipients),
        idempotency_key=idempotency_key or None,
        certificates=[
            Certificate(
                recipient_name=recipient.name,
                recipient_email=str(recipient.email),
                status=CertificateStatus.PENDING.value,
            )
            for recipient in payload.recipients
        ],
    )
    db.add(job)
    try:
        db.commit()  # job + all certificates are saved together, or not at all
    except IntegrityError:
        # Two identical requests raced; the unique key let only one win.
        db.rollback()
        if idempotency_key:
            existing = find_job_by_idempotency_key(db, idempotency_key)
            if existing is not None:
                return existing, False
        raise
    return job, True


def list_jobs(db: Session, limit: int, offset: int) -> list[Job]:
    query = select(Job).order_by(Job.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(query))


def list_job_certificates(
    db: Session, job_id: int, status: CertificateStatus | None
) -> list[Certificate]:
    get_job(db, job_id)  # raises JobNotFoundError (404) if missing
    query = select(Certificate).where(Certificate.job_id == job_id).order_by(Certificate.id)
    if status is not None:
        query = query.where(Certificate.status == status.value)
    return list(db.scalars(query))
