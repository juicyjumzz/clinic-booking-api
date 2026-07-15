"""
Tests for GET /doctors/{id}/availability.
"""

from datetime import datetime, timedelta

from tests.conftest import future_slot_iso


def _future_date_str(days_ahead: int = 30) -> str:
    return (datetime.now() + timedelta(days=days_ahead)).date().isoformat()


def test_availability_lists_all_slots_when_nothing_booked(client, seeded_doctor):
    resp = client.get(
        f"/doctors/{seeded_doctor}/availability", params={"date": _future_date_str()}
    )
    assert resp.status_code == 200
    body = resp.json()
    # Doctor works 09:00-17:00 = 8 hours = 16 half-hour slots.
    assert len(body["available_slots"]) == 16


def test_booked_slot_disappears_from_availability(client, seeded_doctor):
    date_str = _future_date_str()
    client.post(
        "/appointments",
        json={
            "doctor_id": seeded_doctor,
            "patient_id": 1,
            "slot_start": future_slot_iso(hour=9),
        },
    )
    resp = client.get(f"/doctors/{seeded_doctor}/availability", params={"date": date_str})
    assert resp.status_code == 200
    starts = [s["start"] for s in resp.json()["available_slots"]]
    # 09:00 Nairobi == 06:00 UTC should no longer be present.
    assert not any(s.startswith(f"{date_str}T06:00:00") for s in starts)
    assert len(resp.json()["available_slots"]) == 15


def test_cancelled_slot_reappears_in_availability(client, seeded_doctor):
    date_str = _future_date_str()
    book_resp = client.post(
        "/appointments",
        json={
            "doctor_id": seeded_doctor,
            "patient_id": 1,
            "slot_start": future_slot_iso(hour=9),
        },
    )
    appt_id = book_resp.json()["id"]
    client.patch(f"/appointments/{appt_id}/cancel", json={"reason": "x"})

    resp = client.get(f"/doctors/{seeded_doctor}/availability", params={"date": date_str})
    assert len(resp.json()["available_slots"]) == 16


def test_availability_nonexistent_doctor_returns_404(client):
    resp = client.get("/doctors/999999/availability", params={"date": _future_date_str()})
    assert resp.status_code == 404
