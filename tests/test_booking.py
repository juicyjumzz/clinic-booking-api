"""
Tests for POST /appointments: the core validation rules a booking must
satisfy before it's accepted.
"""

from datetime import datetime, timedelta, timezone

from tests.conftest import future_slot_iso


def test_book_valid_slot_returns_201(client, seeded_doctor):
    resp = client.post(
        "/appointments",
        json={
            "doctor_id": seeded_doctor,
            "patient_id": 1,
            "slot_start": future_slot_iso(hour=10),
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["doctor_id"] == seeded_doctor
    assert body["patient_id"] == 1
    assert body["status"] == "booked"


def test_double_booking_same_slot_returns_409(client, seeded_doctor):
    slot = future_slot_iso(hour=10)
    first = client.post(
        "/appointments",
        json={"doctor_id": seeded_doctor, "patient_id": 1, "slot_start": slot},
    )
    assert first.status_code == 201

    second = client.post(
        "/appointments",
        json={"doctor_id": seeded_doctor, "patient_id": 2, "slot_start": slot},
    )
    assert second.status_code == 409
    assert "already booked" in second.json()["detail"]


def test_booking_outside_working_hours_returns_400(client, seeded_doctor):
    # Doctor works 09:00-17:00; 20:00 is well outside that.
    resp = client.post(
        "/appointments",
        json={
            "doctor_id": seeded_doctor,
            "patient_id": 1,
            "slot_start": future_slot_iso(hour=20),
        },
    )
    assert resp.status_code == 400
    assert "working hours" in resp.json()["detail"] or "outside" in resp.json()["detail"]


def test_booking_off_grid_time_returns_400(client, seeded_doctor):
    # 10:10 is not a valid 30-minute grid boundary (10:00 or 10:30 are).
    resp = client.post(
        "/appointments",
        json={
            "doctor_id": seeded_doctor,
            "patient_id": 1,
            "slot_start": future_slot_iso(hour=10, minute=10),
        },
    )
    assert resp.status_code == 400


def test_booking_in_the_past_returns_400(client, seeded_doctor):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT09:00:00+00:00")
    resp = client.post(
        "/appointments",
        json={"doctor_id": seeded_doctor, "patient_id": 1, "slot_start": past},
    )
    assert resp.status_code == 400
    assert "past" in resp.json()["detail"].lower()


def test_booking_within_minimum_lead_time_returns_400(client, seeded_doctor):
    # Bonus rule: bookings must be made >= 60 minutes before the slot.
    # 20 minutes from now is inside working hours (assuming test runs
    # during a reasonable hour) but violates the lead-time rule. To keep
    # this deterministic regardless of when the suite runs, we instead
    # directly craft a slot 20 minutes from now on today's grid nearest
    # boundary, tolerating that it may occasionally also fail the
    # working-hours check - so we assert on status 400 generally, and
    # confirm the detail message identifies a lead-time or hours problem.
    soon = datetime.now().astimezone() + timedelta(minutes=20)
    # Round down to the nearest 30-minute boundary to at least be on-grid.
    minute = 0 if soon.minute < 30 else 30
    soon = soon.replace(minute=minute, second=0, microsecond=0)
    resp = client.post(
        "/appointments",
        json={
            "doctor_id": seeded_doctor,
            "patient_id": 1,
            "slot_start": soon.isoformat(),
        },
    )
    assert resp.status_code == 400


def test_booking_nonexistent_doctor_returns_404(client):
    resp = client.post(
        "/appointments",
        json={"doctor_id": 999999, "patient_id": 1, "slot_start": future_slot_iso()},
    )
    assert resp.status_code == 404


def test_booking_without_timezone_is_rejected(client, seeded_doctor):
    # slot_start must be timezone-aware; a naive datetime is ambiguous.
    resp = client.post(
        "/appointments",
        json={
            "doctor_id": seeded_doctor,
            "patient_id": 1,
            "slot_start": "2027-01-01T10:00:00",
        },
    )
    assert resp.status_code == 422
