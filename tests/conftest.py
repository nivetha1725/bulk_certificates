"""Shared fixtures. Every test gets its own temporary DB and PDF folder."""
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import Base, create_db_engine, create_session_factory
from app.dependencies import get_certificate_generator, get_output_dir, get_session_factory
from app.main import app
from app.models import Certificate, Job
from app.services.certificate_generator import CertificateData, generate_certificate_pdf
from app.utils.constants import CertificateStatus, JobStatus


@pytest.fixture
def session_factory(tmp_path: Path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    yield create_session_factory(engine)
    engine.dispose()


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    path = tmp_path / "generated_certificates"
    path.mkdir()
    return path


@pytest.fixture
def client(session_factory, output_dir: Path):
    """TestClient wired to the temporary DB / folder.

    TestClient runs background tasks before returning the response, so after
    a POST the job has already been processed.
    """
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_output_dir] = lambda: output_dir
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def db_session(session_factory):
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def make_payload():
    def _make(names: list[str] | None = None) -> dict:
        names = names or ["Nivetha L G", "Priya", "Arun"]
        return {
            "event_name": "AI Workshop 2026",
            "event_date": "2026-10-07",
            "organization_name": "ABC Organization",
            "recipients": [
                {"name": name, "email": f"user{i}@example.com"} for i, name in enumerate(names)
            ],
        }

    return _make


@pytest.fixture
def valid_payload(make_payload) -> dict:
    return make_payload()


@pytest.fixture
def fail_for_names(client):
    """Make the generator fail for specific recipient names (test-only).

    Production code is untouched: we override the injected generator with a
    wrapper that raises for chosen names and otherwise calls the real one.
    """

    def _install(*names: str) -> None:
        def flaky_generator(data: CertificateData, output_path: Path) -> None:
            if data.recipient_name in names:
                raise RuntimeError(f"Simulated failure for {data.recipient_name}")
            generate_certificate_pdf(data, output_path)

        app.dependency_overrides[get_certificate_generator] = lambda: flaky_generator

    return _install


@pytest.fixture
def insert_job(db_session):
    """Insert a job (with counters/status of our choice) directly into the DB."""

    def _insert(status: JobStatus, total: int, successful: int = 0, failed: int = 0) -> Job:
        job = Job(
            event_name="Manual Event",
            event_date=date(2026, 10, 7),
            organization_name="ABC Organization",
            status=status.value,
            total_count=total,
            successful_count=successful,
            failed_count=failed,
        )
        job.certificates = [
            Certificate(
                recipient_name=f"Person {i}",
                recipient_email=f"p{i}@example.com",
                status=CertificateStatus.PENDING.value,
            )
            for i in range(total)
        ]
        db_session.add(job)
        db_session.commit()
        return job

    return _insert
