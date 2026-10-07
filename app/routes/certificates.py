import logging
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_output_dir
from app.exceptions import CertificateFileMissingError, CertificateNotAvailableError
from app.services import job_service
from app.services.file_storage import resolve_safe_path
from app.utils.constants import CertificateStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/certificates", tags=["Certificates"])


@router.get(
    "/{certificate_id}",
    summary="Download a generated certificate (PDF)",
    response_class=FileResponse,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "The certificate PDF"},
        404: {"description": "Certificate (or its file) not found"},
        409: {"description": "Certificate exists but has no PDF (failed or not finished yet)"},
    },
)
def download_certificate(
    certificate_id: int,
    db: Session = Depends(get_db),
    output_dir: Path = Depends(get_output_dir),
) -> FileResponse:
    certificate = job_service.get_certificate(db, certificate_id)

    if certificate.status == CertificateStatus.FAILED:
        raise CertificateNotAvailableError(
            f"Certificate generation failed: {certificate.error_message}"
        )
    if certificate.status != CertificateStatus.SUCCESS:
        raise CertificateNotAvailableError(
            f"Certificate is not ready yet (status: {certificate.status})"
        )

    file_path = resolve_safe_path(output_dir, certificate.file_path)
    if file_path is None or not file_path.is_file():
        logger.error("PDF missing on disk for certificate %s", certificate_id)
        raise CertificateFileMissingError()

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"{certificate.certificate_code}.pdf",
    )
