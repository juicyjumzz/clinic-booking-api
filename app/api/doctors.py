"""
Doctor-related endpoints: listing doctors and checking availability.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import DoctorNotFound
from app.models.doctor import Doctor
from app.schemas.doctor import AvailabilityOut, DoctorOut, SlotOut
from app.services.availability import get_available_slots

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=list[DoctorOut])
def list_doctors(db: Session = Depends(get_db)):
    """Not required by the brief, but useful for exploring the API/Swagger
    docs without having to know doctor IDs in advance."""
    return db.scalars(select(Doctor)).all()


@router.get("/{doctor_id}/availability", response_model=AvailabilityOut)
def get_doctor_availability(
    doctor_id: int,
    on_date: date = Query(..., alias="date", description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
):
    try:
        slots = get_available_slots(db, doctor_id, on_date)
    except DoctorNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return AvailabilityOut(
        doctor_id=doctor_id,
        date=on_date.isoformat(),
        available_slots=[
            SlotOut(start=s["start"].isoformat(), end=s["end"].isoformat()) for s in slots
        ],
    )
