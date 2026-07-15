"""
Appointment model.

Concurrency design decision (this is the most important part of this
file - see README "Concurrency" section for the full reasoning):

A naive implementation checks "is this slot free?" and then, in a second
separate step, inserts the new appointment row. Under concurrent load, two
requests can both pass the "is it free?" check before either one has
inserted its row, and both bookings succeed for the same slot. Checking in
application code can never fully close this gap, because there is always a
window between the check and the write.

Instead, we enforce the invariant at the database level with a *partial
unique index* on (doctor_id, slot_start) that only applies to rows where
status = 'booked'. Two properties fall out of this for free:

1. If two requests race to insert a booking for the same slot, the database
   itself rejects the second INSERT with an IntegrityError, no matter how
   the requests interleave. There is no gap for a race condition to exploit,
   because the uniqueness check and the write happen atomically inside the
   database engine.
2. Because the index only covers status='booked' rows, once an appointment
   is cancelled it stops occupying its slot in the eyes of the constraint,
   so the same slot can be freely rebooked - without us needing to delete
   the cancelled row (we want to keep it for history/audit purposes).
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AppointmentStatus(str, enum.Enum):
    BOOKED = "booked"
    CANCELLED = "cancelled"


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)

    # No Patient table exists yet (out of scope for this assessment) - the
    # brief only ever refers to a patient_id, so we model it as a plain
    # integer identifier rather than inventing a Patient model with
    # unspecified fields. This is called out as an assumption in the README.
    patient_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Always UTC, but stored *naive* (no tzinfo) on purpose: SQLite has no
    # native timezone-aware datetime type, and SQLAlchemy's
    # DateTime(timezone=True) on the SQLite dialect silently drops tzinfo
    # on read even though it accepted it on write. Comparing a tz-aware
    # datetime against one that round-tripped back naive is a silent bug
    # (they're never equal, even for the same instant), so instead we
    # standardise on "naive datetime that everyone agrees is UTC" for
    # anything stored here, and only attach/strip tzinfo at the service
    # layer boundary (see app/core/time_utils.py) where we talk to the API.
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AppointmentStatus.BOOKED.value
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: _naive_utc_now(),
    )

    doctor: Mapped["Doctor"] = relationship(back_populates="appointments")

    __table_args__ = (
        Index(
            "uq_doctor_slot_when_booked",
            "doctor_id",
            "slot_start",
            unique=True,
            sqlite_where=text("status = 'booked'"),
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return (
            f"<Appointment id={self.id} doctor_id={self.doctor_id} "
            f"slot_start={self.slot_start} status={self.status}>"
        )
