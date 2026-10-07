from datetime import date
from pathlib import Path

from app.models import Certificate
from app.services.certificate_generator import CertificateData, generate_certificate_pdf
from app.utils.constants import CertificateStatus


def test_generation_creates_pdfs_and_marks_success(client, valid_payload, db_session, output_dir):
    job_id = client.post("/api/v1/jobs", json=valid_payload).json()["job_id"]

    certificates = db_session.query(Certificate).filter_by(job_id=job_id).all()
    assert len(certificates) == 3
    for certificate in certificates:
        assert certificate.status == CertificateStatus.SUCCESS
        assert certificate.error_message is None
        assert certificate.completed_at is not None
        # Relative, server-generated path stored in the DB
        assert certificate.file_path == f"job_{job_id}/{certificate.certificate_code}.pdf"
        pdf_file = output_dir / certificate.file_path
        assert pdf_file.is_file()
        assert pdf_file.read_bytes().startswith(b"%PDF")


def test_files_are_organised_by_job(client, valid_payload, output_dir):
    client.post("/api/v1/jobs", json=valid_payload)
    client.post("/api/v1/jobs", json=valid_payload)

    assert sorted(p.name for p in output_dir.iterdir()) == ["job_1", "job_2"]
    assert sorted(p.name for p in (output_dir / "job_1").iterdir()) == [
        "CERT-000001.pdf", "CERT-000002.pdf", "CERT-000003.pdf",
    ]


def test_certificate_ids_are_unique_across_jobs(client, valid_payload, db_session):
    client.post("/api/v1/jobs", json=valid_payload)
    client.post("/api/v1/jobs", json=valid_payload)

    codes = [c.certificate_code for c in db_session.query(Certificate).all()]
    assert len(codes) == 6
    assert len(set(codes)) == 6


def test_list_certificates_has_download_urls_and_no_file_paths(client, valid_payload, output_dir):
    job_id = client.post("/api/v1/jobs", json=valid_payload).json()["job_id"]

    response = client.get(f"/api/v1/jobs/{job_id}/certificates")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job_id
    assert body["total"] == 3
    first = body["certificates"][0]
    assert first["certificate_code"] == "CERT-000001"
    assert first["recipient_name"] == "Nivetha L G"
    assert first["status"] == "success"
    assert first["download_url"] == f"/api/v1/certificates/{first['certificate_id']}"
    assert first["error_message"] is None
    # No internal filesystem details leak into the response
    assert "file_path" not in first
    assert str(output_dir) not in response.text
    assert ".pdf" not in response.text


def test_list_certificates_status_filter(client, valid_payload):
    job_id = client.post("/api/v1/jobs", json=valid_payload).json()["job_id"]

    ok = client.get(f"/api/v1/jobs/{job_id}/certificates?status=success").json()
    failed = client.get(f"/api/v1/jobs/{job_id}/certificates?status=failed").json()

    assert ok["total"] == 3
    assert failed["total"] == 0
    assert client.get(f"/api/v1/jobs/{job_id}/certificates?status=bogus").status_code == 422


def test_generator_writes_valid_pdf_and_leaves_no_temp_file(tmp_path: Path):
    target = tmp_path / "nested" / "dir" / "CERT-000042.pdf"
    data = CertificateData("CERT-000042", "Nivetha L G", "AI Workshop 2026", date(2026, 10, 7), "ABC Organization")

    generate_certificate_pdf(data, target)

    assert target.read_bytes().startswith(b"%PDF")
    assert [p.name for p in target.parent.iterdir()] == ["CERT-000042.pdf"]


def test_generator_handles_very_long_text(tmp_path: Path):
    data = CertificateData(
        "CERT-000001", "N" * 100, "An Extremely Long Event Name " * 5, date(2026, 1, 1), "Org " * 30
    )
    target = tmp_path / "long.pdf"
    generate_certificate_pdf(data, target)
    assert target.stat().st_size > 0
