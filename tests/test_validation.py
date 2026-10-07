import pytest

from app.utils.constants import MAX_NAME_LENGTH, MAX_RECIPIENTS_PER_JOB


def post(client, payload):
    return client.post("/api/v1/jobs", json=payload)


def error_locations(response) -> list[tuple]:
    return [tuple(err["loc"]) for err in response.json()["detail"]]


def test_empty_name_rejected(client, valid_payload):
    valid_payload["recipients"][0]["name"] = ""
    response = post(client, valid_payload)
    assert response.status_code == 422
    assert ("body", "recipients", 0, "name") in error_locations(response)


def test_whitespace_only_name_rejected(client, valid_payload):
    valid_payload["recipients"][0]["name"] = "     "
    assert post(client, valid_payload).status_code == 422


def test_too_long_name_rejected(client, valid_payload):
    valid_payload["recipients"][0]["name"] = "A" * (MAX_NAME_LENGTH + 1)
    assert post(client, valid_payload).status_code == 422


@pytest.mark.parametrize("bad_email", ["not-an-email", "missing@domain", "@example.com", "", "a b@c.com"])
def test_invalid_email_rejected(client, valid_payload, bad_email):
    valid_payload["recipients"][0]["email"] = bad_email
    response = post(client, valid_payload)
    assert response.status_code == 422
    assert ("body", "recipients", 0, "email") in error_locations(response)


@pytest.mark.parametrize(
    "missing_field", ["event_name", "event_date", "organization_name", "recipients"]
)
def test_missing_required_top_level_field_rejected(client, valid_payload, missing_field):
    del valid_payload[missing_field]
    response = post(client, valid_payload)
    assert response.status_code == 422
    assert ("body", missing_field) in error_locations(response)


def test_missing_recipient_name_and_email_rejected(client, valid_payload):
    valid_payload["recipients"] = [{"email": "a@example.com"}, {"name": "No Email"}]
    response = post(client, valid_payload)
    assert response.status_code == 422
    locations = error_locations(response)
    assert ("body", "recipients", 0, "name") in locations
    assert ("body", "recipients", 1, "email") in locations


def test_empty_recipients_list_rejected(client, valid_payload):
    valid_payload["recipients"] = []
    assert post(client, valid_payload).status_code == 422


def test_too_many_recipients_rejected(client, make_payload):
    payload = make_payload([f"Person {i}" for i in range(MAX_RECIPIENTS_PER_JOB + 1)])
    assert post(client, payload).status_code == 422


@pytest.mark.parametrize("bad_date", ["07-10-2026", "2026-13-45", "tomorrow", ""])
def test_invalid_event_date_rejected(client, valid_payload, bad_date):
    valid_payload["event_date"] = bad_date
    assert post(client, valid_payload).status_code == 422


@pytest.mark.parametrize("field", ["event_name", "organization_name"])
def test_blank_event_or_organization_rejected(client, valid_payload, field):
    valid_payload[field] = "   "
    assert post(client, valid_payload).status_code == 422


def test_invalid_request_creates_nothing(client, valid_payload, db_session):
    from app.models import Job

    valid_payload["recipients"][1]["email"] = "bad"
    post(client, valid_payload)
    assert db_session.query(Job).count() == 0


def test_name_is_trimmed(client, valid_payload, db_session):
    from app.models import Certificate

    valid_payload["recipients"][0]["name"] = "  Nivetha  "
    post(client, valid_payload)
    assert db_session.query(Certificate).order_by(Certificate.id).first().recipient_name == "Nivetha"
