"""
Tests for PATCH /appointments/{id}/cancel and
PATCH /appointments/{id}/reschedule.
"""

from tests.conftest import future_slot_iso


def _book(client, doctor_id, patient_id, hour, minute=0):
    resp = client.post(
        "/appointments",
        json={
            "doctor_id": doctor_id,
            "patient_id": patient_id,
            "slot_start": future_slot_iso(hour=hour, minute=minute),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_cancel_appointment_frees_the_slot(client, seeded_doctor):
    appt = _book(client, seeded_doctor, patient_id=1, hour=9)

    cancel_resp = client.patch(
        f"/appointments/{appt['id']}/cancel", json={"reason": "Feeling better"}
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"
    assert cancel_resp.json()["cancellation_reason"] == "Feeling better"

    # The same slot should now be freely bookable by someone else.
    rebook_resp = client.post(
        "/appointments",
        json={
            "doctor_id": seeded_doctor,
            "patient_id": 2,
            "slot_start": future_slot_iso(hour=9),
        },
    )
    assert rebook_resp.status_code == 201


def test_cancel_already_cancelled_returns_409(client, seeded_doctor):
    appt = _book(client, seeded_doctor, patient_id=1, hour=9)
    first = client.patch(f"/appointments/{appt['id']}/cancel", json={"reason": "x"})
    assert first.status_code == 200

    second = client.patch(f"/appointments/{appt['id']}/cancel", json={"reason": "y"})
    assert second.status_code == 409


def test_cancel_nonexistent_appointment_returns_404(client):
    resp = client.patch("/appointments/999999/cancel", json={"reason": "x"})
    assert resp.status_code == 404


def test_reschedule_moves_appointment_and_frees_old_slot(client, seeded_doctor):
    appt = _book(client, seeded_doctor, patient_id=1, hour=9)

    resp = client.patch(
        f"/appointments/{appt['id']}/reschedule",
        json={"new_slot_start": future_slot_iso(hour=11)},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == appt["id"]

    # Old 09:00 slot should be free again.
    rebook_old = client.post(
        "/appointments",
        json={
            "doctor_id": seeded_doctor,
            "patient_id": 2,
            "slot_start": future_slot_iso(hour=9),
        },
    )
    assert rebook_old.status_code == 201


def test_reschedule_onto_taken_slot_returns_409_and_keeps_original(client, seeded_doctor):
    appt = _book(client, seeded_doctor, patient_id=1, hour=9)
    _book(client, seeded_doctor, patient_id=2, hour=11)  # occupies 11:00

    resp = client.patch(
        f"/appointments/{appt['id']}/reschedule",
        json={"new_slot_start": future_slot_iso(hour=11)},
    )
    assert resp.status_code == 409

    # Original appointment must be untouched: still booked at 09:00.
    upcoming = client.get("/patients/1/appointments").json()
    assert len(upcoming) == 1
    assert upcoming[0]["id"] == appt["id"]
    assert upcoming[0]["status"] == "booked"
    assert "09:00" in upcoming[0]["slot_start"] or upcoming[0]["slot_start"].endswith(
        "T06:00:00"
    )


def test_reschedule_cancelled_appointment_returns_409(client, seeded_doctor):
    appt = _book(client, seeded_doctor, patient_id=1, hour=9)
    client.patch(f"/appointments/{appt['id']}/cancel", json={"reason": "x"})

    resp = client.patch(
        f"/appointments/{appt['id']}/reschedule",
        json={"new_slot_start": future_slot_iso(hour=11)},
    )
    assert resp.status_code == 409


def test_reschedule_nonexistent_appointment_returns_404(client):
    resp = client.patch(
        "/appointments/999999/reschedule",
        json={"new_slot_start": future_slot_iso(hour=11)},
    )
    assert resp.status_code == 404
