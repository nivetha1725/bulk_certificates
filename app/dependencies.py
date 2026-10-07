"""FastAPI dependencies.

Everything environment-specific (DB, PDF generator, storage folder) is
injected here, so tests can swap each piece with dependency_overrides.
"""
from collections.abc import Iterator
from pathlib import Path

from fastapi import Depends
from sqlalchemy.orm import Session

from app import database
from app.config import settings
from app.database import SessionFactory
from app.services.certificate_generator import generate_certificate_pdf
from app.services.job_processor import CertificateGenerator


def get_session_factory() -> SessionFactory:
    return database.SessionLocal


def get_db(session_factory: SessionFactory = Depends(get_session_factory)) -> Iterator[Session]:
    """One session per request, always closed afterwards."""
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def get_certificate_generator() -> CertificateGenerator:
    return generate_certificate_pdf


def get_output_dir() -> Path:
    return settings.certificates_dir
