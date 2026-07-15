"""
Availability calculation: given a doctor and a date, work out which
30-minute slots are still bookable.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import DoctorNotFound
from app.core.time_utils import slot_grid_for_date
from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor

settings = get_settings()


def get_available_slots(db: Session, doctor_id: int, on_date: date) -> list[dict]:
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise DoctorNotFound(f"No doctor with id {doctor_id}")

    all_slots = slot_grid_for_date(
        doctor.work_start, doctor.work_end, on_date, settings.slot_minutes
    )

    booked_starts = set(
        db.scalars(
            select(Appointment.slot_start).where(
                Appointment.doctor_id == doctor_id,
                Appointment.status == AppointmentStatus.BOOKED.value,
            )
        ).all()
    )

    available = [s for s in all_slots if s.replace(tzinfo=None) not in booked_starts]
    step = timedelta(minutes=settings.slot_minutes)

    return [{"start": s, "end": s + step} for s in available]
