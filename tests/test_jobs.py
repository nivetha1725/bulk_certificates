from app.models import Certificate, Job
from app.utils.constants import JobStatus


def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "message": "Bulk Certificate Generator API is running",
    }


def test_create_job_returns_job_id_immediately(client, valid_payload, db_session):
    response = client.post("/api/v1/jobs", json=valid_payload)

    assert response.status_code == 202
    body = response.json()
    assert body["job_id"] == 1
    assert body["status"] == "queued"  # response is built before background work
    assert body["total"] == 3
    assert body["message"] == "Certificate generation job created successfully"

    assert db_session.query(Job).count() == 1
    assert db_session.query(Certificate).filter_by(job_id=body["job_id"]).count() == 3


def test_certificate_records_store_recipient_data(client, valid_payload, db_session):
    client.post("/api/v1/jobs", json=valid_payload)

    certificates = db_session.query(Certificate).order_by(Certificate.id).all()
    assert [c.recipient_name for c in certificates] == ["Nivetha L G", "Priya", "Arun"]
    assert certificates[0].recipient_email == "user0@example.com"
    assert [c.certificate_code for c in certificates] == ["CERT-000001", "CERT-000002", "CERT-000003"]


def test_get_job_status_after_processing(client, valid_payload):
    job_id = client.post("/api/v1/jobs", json=valid_payload).json()["job_id"]

    body = client.get(f"/api/v1/jobs/{job_id}").json()

    assert body["job_id"] == job_id
    assert body["status"] == "completed"
    assert (body["total"], body["successful"], body["failed"]) == (3, 3, 0)
    assert body["progress_percentage"] == 100
    assert body["completed_at"] is not None


def test_get_unknown_job_returns_404(client):
    response = client.get("/api/v1/jobs/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_jobs_most_recent_first(client, valid_payload):
    client.post("/api/v1/jobs", json=valid_payload)
    client.post("/api/v1/jobs", json=valid_payload)

    response = client.get("/api/v1/jobs")

    assert response.status_code == 200
    assert [j["job_id"] for j in response.json()] == [2, 1]


def test_list_certificates_unknown_job_returns_404(client):
    assert client.get("/api/v1/jobs/999/certificates").status_code == 404


# ---- progress / status states -------------------------------------------------


def test_queued_job_has_zero_progress(client, insert_job):
    job = insert_job(JobStatus.QUEUED, total=10)

    body = client.get(f"/api/v1/jobs/{job.id}").json()

    assert body["status"] == "queued"
    assert body["progress_percentage"] == 0
    assert body["completed_at"] is None


def test_processing_job_progress_uses_successful_plus_failed(client, insert_job):
    job = insert_job(JobStatus.PROCESSING, total=100, successful=45, failed=2)

    body = client.get(f"/api/v1/jobs/{job.id}").json()

    assert body["status"] == "processing"
    assert (body["total"], body["successful"], body["failed"]) == (100, 45, 2)
    assert body["progress_percentage"] == 47


def test_progress_example_from_spec(client, insert_job):
    job = insert_job(JobStatus.PROCESSING, total=100, successful=45, failed=5)
    assert client.get(f"/api/v1/jobs/{job.id}").json()["progress_percentage"] == 50


# ---- idempotency --------------------------------------------------------------


def test_same_idempotency_key_does_not_create_duplicate_job(client, valid_payload, db_session):
    headers = {"Idempotency-Key": "my-unique-request-1"}

    first = client.post("/api/v1/jobs", json=valid_payload, headers=headers).json()
    second = client.post("/api/v1/jobs", json=valid_payload, headers=headers).json()

    assert first["job_id"] == second["job_id"]
    assert db_session.query(Job).count() == 1
    assert db_session.query(Certificate).count() == 3


def test_different_idempotency_keys_create_separate_jobs(client, valid_payload, db_session):
    client.post("/api/v1/jobs", json=valid_payload, headers={"Idempotency-Key": "a"})
    client.post("/api/v1/jobs", json=valid_payload, headers={"Idempotency-Key": "b"})
    assert db_session.query(Job).count() == 2
