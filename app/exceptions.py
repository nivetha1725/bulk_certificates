"""Domain exceptions. Each one maps to a clean HTTP response in main.py."""


class AppError(Exception):
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class JobNotFoundError(AppError):
    status_code = 404

    def __init__(self, job_id: int) -> None:
        super().__init__(f"Job {job_id} not found")


class CertificateNotFoundError(AppError):
    status_code = 404

    def __init__(self, certificate_id: int) -> None:
        super().__init__(f"Certificate {certificate_id} not found")


class CertificateNotAvailableError(AppError):
    """The certificate exists but has no PDF (failed, pending or processing)."""

    status_code = 409


class CertificateFileMissingError(AppError):
    """The database says the PDF exists but the file is not on disk."""

    status_code = 404

    def __init__(self) -> None:
        super().__init__("Certificate file is missing on the server")
