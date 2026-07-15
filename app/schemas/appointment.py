"""
Pydantic (API) schemas for appointments: request bodies and response
shapes for booking, cancelling, and rescheduling.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppointmentCreate(BaseModel):
    doctor_id: int
    patient_id: int
    slot_start: datetime = Field(
        ..., description="ISO 8601 datetime, must include a timezone offset."
    )

    @field_validator("slot_start")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError(
                "slot_start must include a timezone offset, e.g. "
                "'2026-07-20T09:00:00+03:00' or '2026-07-20T06:00:00Z'"
            )
        return v


class AppointmentCancel(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class AppointmentReschedule(BaseModel):
    new_slot_start: datetime = Field(
        ..., description="ISO 8601 datetime, must include a timezone offset."
    )

    @field_validator("new_slot_start")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError(
                "new_slot_start must include a timezone offset, e.g. "
                "'2026-07-20T09:00:00+03:00' or '2026-07-20T06:00:00Z'"
            )
        return v


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    patient_id: int
    slot_start: datetime
    slot_end: datetime
    status: str
    cancellation_reason: str | None = None
    created_at: datetime
    updated_at: datetime
