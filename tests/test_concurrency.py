"""
Concurrency test.

This directly exercises the failure mode a naive "check then insert"
implementation is vulnerable to: many requests racing to book the exact
same slot for the exact same doctor at (as close to) the exact same time
as we can arrange in a test. With the partial unique index + insert-and-
catch-IntegrityError approach used in app/services/appointments.py,
exactly one request must succeed no matter how the threads interleave.

This uses real OS threads (not just async concurrency) hitting the same
on-disk SQLite database, via a barrier that releases every thread at
(almost) the same instant, to make the race as tight as possible.
"""

import threading

from tests.conftest import future_slot_iso


def test_concurrent_bookings_for_same_slot_only_one_succeeds(client, seeded_doctor):
    slot = future_slot_iso(hour=9)
    num_threads = 12
    barrier = threading.Barrier(num_threads)
    results = [None] * num_threads

    def attempt_booking(i):
        barrier.wait()  # release all threads at (almost) the same instant
        resp = client.post(
            "/appointments",
            json={"doctor_id": seeded_doctor, "patient_id": i, "slot_start": slot},
        )
        results[i] = resp.status_code

    threads = [threading.Thread(target=attempt_booking, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = results.count(201)
    conflicts = results.count(409)

    assert successes == 1, (
        f"Expected exactly one successful booking under concurrent load, got "
        f"{successes}. Results: {results}"
    )
    assert conflicts == num_threads - 1

    # Sanity check: exactly one appointment actually exists in the DB for
    # this slot/doctor, not just that the API reported one success. Parse
    # properly rather than string-slicing across timezones (the local slot
    # time and the UTC time the API reports are offset by Nairobi's fixed
    # +03:00, so naive substring matching would compare the wrong thing).
    from datetime import datetime as dt
    from datetime import timezone as _tz

    expected_utc_start = dt.fromisoformat(slot).astimezone(_tz.utc)

    available = client.get(
        f"/doctors/{seeded_doctor}/availability",
        params={"date": slot.split("T")[0]},
    ).json()
    remaining_starts = {dt.fromisoformat(s["start"]) for s in available["available_slots"]}
    assert expected_utc_start not in remaining_starts
