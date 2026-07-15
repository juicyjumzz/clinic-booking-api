"""
Pydantic (API) schemas for doctors.

Kept separate from the SQLAlchemy models in app/models - the DB model
describes how data is stored, these describe what the API accepts and
returns. Collapsing the two together tends to leak database concerns
(and, worse, database-only fields like personal contact info) into the
public API surface.
"""

from datetime import time

from pydantic import BaseModel, ConfigDict


class DoctorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    specialty: str
    work_start: time
    work_end: time


class SlotOut(BaseModel):
    """A single bookable (or already-booked) slot for a doctor on a date."""

    start: str  # ISO 8601 UTC datetime string
    end: str  # ISO 8601 UTC datetime string


class AvailabilityOut(BaseModel):
    doctor_id: int
    date: str  # ISO 8601 date, e.g. "2026-07-20"
    available_slots: list[SlotOut]
