from app.models import Certificate, Job
from app.utils.constants import CertificateStatus, JobStatus


def certificates_by_name(db_session) -> dict[str, Certificate]:
    return {c.recipient_name: c for c in db_session.query(Certificate).all()}


def test_one_failure_does_not_stop_the_batch(client, make_payload, fail_for_names, db_session, output_dir):
    fail_for_names("Recipient B")
    payload = make_payload(["Recipient A", "Recipient B", "Recipient C"])

    job_id = client.post("/api/v1/jobs", json=payload).json()["job_id"]

    certs = certificates_by_name(db_session)
    assert certs["Recipient A"].status == CertificateStatus.SUCCESS
    assert certs["Recipient B"].status == CertificateStatus.FAILED
    assert certs["Recipient C"].status == CertificateStatus.SUCCESS  # processed AFTER the failure

    assert (output_dir / certs["Recipient A"].file_path).is_file()
    assert (output_dir / certs["Recipient C"].file_path).is_file()
    assert certs["Recipient B"].file_path is None

    job = db_session.get(Job, job_id)
    assert (job.total_count, job.successful_count, job.failed_count) == (3, 2, 1)
    assert job.status == JobStatus.PARTIALLY_COMPLETED
    assert job.completed_at is not None


def test_failure_message_is_stored_on_certificate(client, make_payload, fail_for_names, db_session):
    fail_for_names("Recipient B")
    client.post("/api/v1/jobs", json=make_payload(["Recipient A", "Recipient B"]))

    failed = certificates_by_name(db_session)["Recipient B"]
    assert failed.completed_at is not None
    assert "Simulated failure for Recipient B" in failed.error_message


def test_five_recipients_one_failure(client, make_payload, fail_for_names, db_session):
    """The exact example from the assignment: 4 succeed, 1 fails."""
    fail_for_names("Recipient 3")
    payload = make_payload([f"Recipient {i}" for i in range(1, 6)])

    job_id = client.post("/api/v1/jobs", json=payload).json()["job_id"]

    body = client.get(f"/api/v1/jobs/{job_id}").json()
    assert (body["total"], body["successful"], body["failed"]) == (5, 4, 1)
    assert body["status"] == "partially_completed"
    assert body["progress_percentage"] == 100


def test_all_failures_mark_job_failed(client, make_payload, fail_for_names):
    fail_for_names("Recipient A", "Recipient B")

    job_id = client.post("/api/v1/jobs", json=make_payload(["Recipient A", "Recipient B"])).json()["job_id"]

    body = client.get(f"/api/v1/jobs/{job_id}").json()
    assert body["status"] == "failed"
    assert (body["successful"], body["failed"]) == (0, 2)
    assert body["progress_percentage"] == 100


def test_failed_certificates_listed_with_error_and_no_download_url(client, make_payload, fail_for_names):
    fail_for_names("Recipient B")
    job_id = client.post("/api/v1/jobs", json=make_payload(["Recipient A", "Recipient B"])).json()["job_id"]

    items = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["certificates"]
    by_name = {item["recipient_name"]: item for item in items}

    assert by_name["Recipient A"]["download_url"] is not None
    assert by_name["Recipient A"]["error_message"] is None
    assert by_name["Recipient B"]["status"] == "failed"
    assert by_name["Recipient B"]["download_url"] is None
    assert "Simulated failure" in by_name["Recipient B"]["error_message"]

    only_failed = client.get(f"/api/v1/jobs/{job_id}/certificates?status=failed").json()
    assert only_failed["total"] == 1


def test_failure_message_does_not_leak_storage_path(client, make_payload, output_dir, db_session):
    from app.dependencies import get_certificate_generator
    from app.main import app

    def broken_generator(data, output_path):
        raise OSError(f"cannot write {output_path}")

    app.dependency_overrides[get_certificate_generator] = lambda: broken_generator
    client.post("/api/v1/jobs", json=make_payload(["Only One"]))

    message = db_session.query(Certificate).one().error_message
    assert str(output_dir) not in message
    assert "<storage>" in message


def test_real_unsupported_characters_fail_only_that_certificate(client, make_payload, db_session):
    """A genuine (not simulated) failure: the built-in font is Latin-only.

    Uses the REAL generator. The Tamil name must fail with a clear message while
    the recipients before and after it still succeed.
    """
    payload = make_payload(["José Müller", "நிவேதா", "Arun"])  # accents are fine, Tamil is not

    job_id = client.post("/api/v1/jobs", json=payload).json()["job_id"]

    certs = certificates_by_name(db_session)
    assert certs["José Müller"].status == CertificateStatus.SUCCESS
    assert certs["Arun"].status == CertificateStatus.SUCCESS
    assert certs["நிவேதா"].status == CertificateStatus.FAILED
    assert "UnsupportedCharactersError" in certs["நிவேதா"].error_message
    assert "Latin" in certs["நிவேதா"].error_message
    job = db_session.get(Job, job_id)
    assert (job.successful_count, job.failed_count) == (2, 1)
    assert job.status == JobStatus.PARTIALLY_COMPLETED
