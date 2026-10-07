from app.models import Certificate
from app.utils.constants import JobStatus


def test_download_successful_certificate(client, valid_payload):
    client.post("/api/v1/jobs", json=valid_payload)

    response = client.get("/api/v1/certificates/1")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "CERT-000001.pdf" in response.headers["content-disposition"]


def test_download_url_from_listing_works(client, valid_payload):
    job_id = client.post("/api/v1/jobs", json=valid_payload).json()["job_id"]
    url = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["certificates"][1]["download_url"]

    response = client.get(url)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def test_missing_certificate_returns_404(client):
    response = client.get("/api/v1/certificates/12345")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_failed_certificate_cannot_be_downloaded(client, make_payload, fail_for_names):
    fail_for_names("Recipient B")
    client.post("/api/v1/jobs", json=make_payload(["Recipient A", "Recipient B"]))

    response = client.get("/api/v1/certificates/2")

    assert response.status_code == 409
    assert "failed" in response.json()["detail"].lower()
    assert response.headers["content-type"] == "application/json"


def test_pending_certificate_is_not_downloadable(client, insert_job):
    job = insert_job(JobStatus.QUEUED, total=1)  # certificate stays PENDING

    response = client.get(f"/api/v1/certificates/{job.certificates[0].id}")

    assert response.status_code == 409
    assert "not ready" in response.json()["detail"].lower()


def test_missing_pdf_file_returns_404_without_path_leak(client, valid_payload, output_dir):
    client.post("/api/v1/jobs", json=valid_payload)
    (output_dir / "job_1" / "CERT-000001.pdf").unlink()

    response = client.get("/api/v1/certificates/1")

    assert response.status_code == 404
    assert response.json() == {"detail": "Certificate file is missing on the server"}


def test_path_traversal_in_db_value_is_never_served(client, valid_payload, db_session, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")
    client.post("/api/v1/jobs", json=valid_payload)
    certificate = db_session.get(Certificate, 1)
    certificate.file_path = "../secret.txt"
    db_session.commit()

    response = client.get("/api/v1/certificates/1")

    assert response.status_code == 404
    assert b"top secret" not in response.content


def test_non_integer_certificate_id_returns_422(client):
    assert client.get("/api/v1/certificates/abc").status_code == 422


def test_database_error_returns_500_without_details(client):
    from sqlalchemy.exc import OperationalError

    from app.dependencies import get_db
    from app.main import app

    def broken_db():
        raise OperationalError("SELECT secret FROM table", {}, Exception("boom"))
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = broken_db
    response = client.get("/api/v1/jobs/1")

    assert response.status_code == 500
    assert response.json() == {"detail": "A database error occurred"}
