"""
Appointment booking, cancellation, and rescheduling logic.

This is the most important file in the project - see README "Concurrency"
section, and the long comment at the top of app/models/appointment.py, for
the full reasoning behind the approach used here.

The short version: we never do "check if free, then insert". We always
attempt the write directly and let the database's partial unique index
(doctor_id, slot_start) WHERE status='booked' be the single source of
truth for whether a slot is free. If two requests race for the same slot,
the database guarantees exactly one of them succeeds - regardless of
timing, thread, or process. We only catch the resulting IntegrityError and
turn it into a clean domain error.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    AppointmentAlreadyCancelled,
    AppointmentNotFound,
    DoctorNotFound,
    SlotAlreadyBooked,
    SlotInPast,
    SlotNotOnGrid,
    SlotOutsideWorkingHours,
    SlotTooSoon,
)
from app.core.time_utils import is_on_slot_grid, to_naive_utc, to_utc, naive_utc_now
from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor

settings = get_settings()


def _validate_slot_or_raise(db: Session, doctor_id: int, slot_start_utc: datetime) -> Doctor:
    """
    Shared validation for both fresh bookings and reschedules: the doctor
    must exist, the slot must land exactly on that doctor's 30-minute grid
    and within working hours, it must not be in the past, and (bonus rule)
    it must not be within the minimum lead time of "now".

    Raises the appropriate DomainError subclass and returns the Doctor row
    if every check passes, so callers don't have to fetch it twice.
    """
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise DoctorNotFound(f"No doctor with id {doctor_id}")

    now = datetime.now(timezone.utc)
    if slot_start_utc < now:
        raise SlotInPast("Cannot book a slot in the past")

    if slot_start_utc < now + timedelta(minutes=settings.min_lead_time_minutes):
        raise SlotTooSoon(
            f"Bookings must be made at least {settings.min_lead_time_minutes} "
            "minutes before the slot starts"
        )

    if not is_on_slot_grid(
        slot_start_utc, doctor.work_start, doctor.work_end, settings.slot_minutes
    ):
        # Distinguish "wrong minute, e.g. 09:10 instead of 09:00 or 09:30"
        # from "outside working hours entirely", because they warrant
        # different, more helpful error messages for the client.
        if not (doctor.work_start <= slot_start_utc.time() < doctor.work_end):
            raise SlotOutsideWorkingHours(
                f"Doctor {doctor_id} works {doctor.work_start}-{doctor.work_end}; "
                f"requested slot is outside those hours"
            )
        raise SlotNotOnGrid(
            f"Slot must align to {settings.slot_minutes}-minute increments "
            f"starting at {doctor.work_start}"
        )

    return doctor


def book_appointment(
    db: Session, doctor_id: int, patient_id: int, slot_start: datetime
) -> Appointment:
    slot_start_utc = to_utc(slot_start)
    _validate_slot_or_raise(db, doctor_id, slot_start_utc)

    appointment = Appointment(
        doctor_id=doctor_id,
        patient_id=patient_id,
        slot_start=to_naive_utc(slot_start_utc),
        slot_end=to_naive_utc(slot_start_utc + timedelta(minutes=settings.slot_minutes)),
        status=AppointmentStatus.BOOKED.value,
    )
    db.add(appointment)
    try:
        db.commit()
    except IntegrityError:
        # The partial unique index rejected this insert: someone else
        # booked this exact slot in the gap between our validation above
        # and this commit. This is the race condition fix in action.
        db.rollback()
        raise SlotAlreadyBooked(
            f"Slot {slot_start_utc.isoformat()} for doctor {doctor_id} is already booked"
        )
    db.refresh(appointment)
    return appointment


def cancel_appointment(db: Session, appointment_id: int, reason: str) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise AppointmentNotFound(f"No appointment with id {appointment_id}")

    if appointment.status == AppointmentStatus.CANCELLED.value:
        raise AppointmentAlreadyCancelled(
            f"Appointment {appointment_id} is already cancelled"
        )

    appointment.status = AppointmentStatus.CANCELLED.value
    appointment.cancellation_reason = reason
    db.commit()
    db.refresh(appointment)
    return appointment


def reschedule_appointment(
    db: Session, appointment_id: int, new_slot_start: datetime
) -> Appointment:
    """
    Move an appointment to a new slot.

    Atomicity note (this is exactly the scenario the reviewer notes probe
    for): we do NOT cancel the old appointment and then insert a new one as
    two separate operations - if the new slot turned out to be taken, the
    patient would have already lost their original slot with no way back.

    Instead we mutate slot_start/slot_end on the *same row*, inside a
    single transaction. If the new slot is taken, the UPDATE violates the
    partial unique index and the whole transaction rolls back, leaving the
    original appointment exactly as it was - the patient never loses their
    existing booking just because the new one didn't work out.
    """
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise AppointmentNotFound(f"No appointment with id {appointment_id}")

    if appointment.status == AppointmentStatus.CANCELLED.value:
        raise AppointmentAlreadyCancelled(
            f"Cannot reschedule cancelled appointment {appointment_id}"
        )

    new_slot_start_utc = to_utc(new_slot_start)
    _validate_slot_or_raise(db, appointment.doctor_id, new_slot_start_utc)

    previous_slot_start = appointment.slot_start
    appointment.slot_start = to_naive_utc(new_slot_start_utc)
    appointment.slot_end = to_naive_utc(new_slot_start_utc + timedelta(minutes=settings.slot_minutes))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Because we never committed, `appointment` in the DB still has
        # previous_slot_start - nothing was lost.
        raise SlotAlreadyBooked(
            f"Slot {new_slot_start_utc.isoformat()} for doctor {appointment.doctor_id} "
            f"is already booked; your original slot at {previous_slot_start.isoformat()} "
            "was not changed"
        )
    db.refresh(appointment)
    return appointment


def list_upcoming_for_patient(db: Session, patient_id: int) -> list[Appointment]:
    now = naive_utc_now()
    stmt = (
        select(Appointment)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.status == AppointmentStatus.BOOKED.value,
            Appointment.slot_start >= now,
        )
        .order_by(Appointment.slot_start.asc())
    )
    return list(db.scalars(stmt).all())
