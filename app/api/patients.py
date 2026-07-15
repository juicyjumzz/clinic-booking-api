"""
Patient-related endpoints.

Bonus requirement: GET /patients/{id}/appointments - upcoming appointments
sorted by date. There's no Patient model (see note in
app/models/appointment.py) so this simply filters appointments by
patient_id; nothing here asserts the patient_id "exists" since patients
aren't a first-class entity in this system.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.appointment import AppointmentOut
from app.services.appointments import list_upcoming_for_patient

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/{patient_id}/appointments", response_model=list[AppointmentOut])
def get_upcoming_appointments(patient_id: int, db: Session = Depends(get_db)):
    return list_upcoming_for_patient(db, patient_id)
