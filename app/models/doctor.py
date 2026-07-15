"""
Doctor model.

Deliberately minimal: only the fields the booking system actually needs.
We do NOT store personal contact details (personal phone, personal email)
on this model. That's a conscious decision, not an oversight - a booking
API has no business leaking a doctor's private phone number to whichever
client calls GET /doctors/{id}/availability. If the clinic later needs
doctor contact info for internal staff tooling, that belongs behind a
separate, authenticated, internal-only endpoint - not the public API.
"""

from datetime import time

from sqlalchemy import String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    specialty: Mapped[str] = mapped_column(String(120), nullable=False, default="General Practice")

    # Working hours, stored as plain clock times in the clinic's local
    # timezone (see app/core/time_utils.py for how these are interpreted).
    work_start: Mapped[time] = mapped_column(Time, nullable=False)
    work_end: Mapped[time] = mapped_column(Time, nullable=False)

    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Doctor id={self.id} name={self.full_name!r}>"
