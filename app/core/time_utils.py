"""
Timezone and slot-grid helpers.

Design decision (documented in README): every datetime that touches the
database or crosses a process boundary is UTC and timezone-aware. Doctors'
working hours are defined as plain clock times (e.g. 09:00) in the clinic's
local timezone, because "9am" is meaningful to a human receptionist typing
in working hours, not "06:00 UTC". These two representations meet in the
functions below.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings

settings = get_settings()


def clinic_tz() -> ZoneInfo:
    return ZoneInfo(settings.clinic_timezone)


def to_utc(dt: datetime) -> datetime:
    """
    Normalise any timezone-aware datetime to UTC. Raises ValueError if the
    datetime is naive (has no timezone), because a naive datetime is
    ambiguous and we never want to guess what timezone the caller meant.
    """
    if dt.tzinfo is None:
        raise ValueError("Datetime must be timezone-aware")
    return dt.astimezone(ZoneInfo("UTC"))


def to_naive_utc(dt: datetime) -> datetime:
    """
    Convert a timezone-aware datetime to UTC and then strip the tzinfo,
    for storage in the database. See the comment on Appointment.slot_start
    in app/models/appointment.py for why we do this.
    """
    return to_utc(dt).replace(tzinfo=None)


def naive_utc_now() -> datetime:
    """The current instant, as a naive-UTC datetime - i.e. directly
    comparable to values read back from the database."""
    return datetime.now(ZoneInfo("UTC")).replace(tzinfo=None)


def slot_grid_for_date(
    work_start: time, work_end: time, on_date: date, slot_minutes: int
) -> list[datetime]:
    """
    Build the full list of slot start times (as UTC-aware datetimes) for a
    single doctor on a single calendar date, based on that doctor's working
    hours in clinic-local time.

    Example: work_start=09:00, work_end=12:00, slot_minutes=30 produces
    slots at 09:00, 09:30, 10:00, 10:30, 11:00, 11:30 (local time), each
    converted to UTC. 12:00 itself is excluded because a slot starting at
    12:00 would end at 12:30, which is past work_end.
    """
    tz = clinic_tz()
    local_start = datetime.combine(on_date, work_start, tzinfo=tz)
    local_end = datetime.combine(on_date, work_end, tzinfo=tz)

    slots: list[datetime] = []
    cursor = local_start
    step = timedelta(minutes=slot_minutes)
    while cursor + step <= local_end:
        slots.append(cursor.astimezone(ZoneInfo("UTC")))
        cursor += step
    return slots


def is_on_slot_grid(
    slot_start_utc: datetime, work_start: time, work_end: time, slot_minutes: int
) -> bool:
    """
    Check whether a proposed UTC slot_start falls exactly on the doctor's
    slot grid for whatever local date it lands on, and fully within working
    hours (i.e. the slot must also *end* by work_end).
    """
    tz = clinic_tz()
    local_dt = slot_start_utc.astimezone(tz)
    local_date = local_dt.date()
    valid_slots_local = {
        s.astimezone(tz) for s in slot_grid_for_date(work_start, work_end, local_date, slot_minutes)
    }
    return local_dt in valid_slots_local
