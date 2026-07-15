"""
Appointment endpoints: book, cancel, reschedule.

Every domain exception raised by the service layer is translated to a
specific HTTP status code here, with a clear message body. Mapping:

  DoctorNotFound              -> 404
  AppointmentNotFound         -> 404
  SlotInPast                  -> 400
  SlotTooSoon                 -> 400
  SlotOutsideWorkingHours     -> 400
  SlotNotOnGrid               -> 400
  SlotAlreadyBooked           -> 409 (Conflict - the right code for "someone
                                       else already has this resource")
  AppointmentAlreadyCancelled -> 409 (Conflict - the appointment exists but
                                       is not in a state that allows this
                                       operation)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
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
from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentOut,
    AppointmentReschedule,
)
from app.services.appointments import (
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])

_BAD_REQUEST_ERRORS = (SlotInPast, SlotTooSoon, SlotOutsideWorkingHours, SlotNotOnGrid)


@router.post("", response_model=AppointmentOut, status_code=201)
def create_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    try:
        appointment = book_appointment(
            db, payload.doctor_id, payload.patient_id, payload.slot_start
        )
    except DoctorNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except _BAD_REQUEST_ERRORS as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except SlotAlreadyBooked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return appointment


@router.patch("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel(appointment_id: int, payload: AppointmentCancel, db: Session = Depends(get_db)):
    try:
        appointment = cancel_appointment(db, appointment_id, payload.reason)
    except AppointmentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except AppointmentAlreadyCancelled as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return appointment


@router.patch("/{appointment_id}/reschedule", response_model=AppointmentOut)
def reschedule(
    appointment_id: int, payload: AppointmentReschedule, db: Session = Depends(get_db)
):
    try:
        appointment = reschedule_appointment(db, appointment_id, payload.new_slot_start)
    except (AppointmentNotFound, DoctorNotFound) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except AppointmentAlreadyCancelled as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except _BAD_REQUEST_ERRORS as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except SlotAlreadyBooked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return appointment
