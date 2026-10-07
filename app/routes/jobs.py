from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query
from sqlalchemy.orm import Session

from app.database import SessionFactory
from app.dependencies import (
    get_certificate_generator,
    get_db,
    get_output_dir,
    get_session_factory,
)
from app.schemas.certificate import CertificateListResponse, CertificateResponse
from app.schemas.job import JobCreatedResponse, JobCreateRequest, JobStatusResponse
from app.services import job_service
from app.services.job_processor import CertificateGenerator, process_job
from app.utils.constants import MAX_IDEMPOTENCY_KEY_LENGTH, CertificateStatus

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobCreatedResponse,
    status_code=202,
    summary="Create a bulk certificate generation job",
    description=(
        "Validates the request, stores a job with one PENDING certificate per recipient, "
        "starts generation in the background and returns the job ID immediately. "
        "Poll `GET /api/v1/jobs/{job_id}` for progress.\n\n"
        "Optional `Idempotency-Key` header: repeating a request with the same key returns "
        "the original job instead of creating a duplicate."
    ),
)
def create_job(
    payload: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory: SessionFactory = Depends(get_session_factory),
    generator: CertificateGenerator = Depends(get_certificate_generator),
    output_dir: Path = Depends(get_output_dir),
    idempotency_key: Annotated[
        str | None, Header(max_length=MAX_IDEMPOTENCY_KEY_LENGTH)
    ] = None,
) -> JobCreatedResponse:
    job, created = job_service.create_job(db, payload, idempotency_key)
    if created:
        # The background task opens its own DB session (see job_processor).
        background_tasks.add_task(process_job, job.id, session_factory, generator, output_dir)
        message = "Certificate generation job created successfully"
    else:
        message = "A job with this Idempotency-Key already exists; returning it"
    return JobCreatedResponse(
        job_id=job.id, status=job.status, total=job.total_count, message=message
    )


@router.get(
    "",
    response_model=list[JobStatusResponse],
    summary="List jobs",
    description="Most recent jobs first.",
)
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[JobStatusResponse]:
    return [JobStatusResponse.from_model(job) for job in job_service.list_jobs(db, limit, offset)]


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status and progress",
    description="progress_percentage = (successful + failed) / total * 100.",
    responses={404: {"description": "Job not found"}},
)
def get_job_status(job_id: int, db: Session = Depends(get_db)) -> JobStatusResponse:
    return JobStatusResponse.from_model(job_service.get_job(db, job_id))


@router.get(
    "/{job_id}/certificates",
    response_model=CertificateListResponse,
    summary="List certificates of a job",
    description=(
        "Returns every certificate of the job. Failed ones include `error_message`; "
        "successful ones include a `download_url`. Use `?status=failed` to filter."
    ),
    responses={404: {"description": "Job not found"}},
)
def list_job_certificates(
    job_id: int,
    status: CertificateStatus | None = Query(None, description="Optional status filter"),
    db: Session = Depends(get_db),
) -> CertificateListResponse:
    certificates = job_service.list_job_certificates(db, job_id, status)
    return CertificateListResponse(
        job_id=job_id,
        total=len(certificates),
        certificates=[CertificateResponse.from_model(c) for c in certificates],
    )
