"""
Domain-level exceptions.

Services raise these instead of raising HTTPException directly, which keeps
the business logic layer independent of FastAPI. The API layer (app/api/*)
is responsible for translating each of these into the correct HTTP status
code and error body.
"""


class DomainError(Exception):
    """Base class for all expected, user-facing business rule violations."""


class DoctorNotFound(DomainError):
    pass


class AppointmentNotFound(DomainError):
    pass


class SlotOutsideWorkingHours(DomainError):
    pass


class SlotNotOnGrid(DomainError):
    pass


class SlotInPast(DomainError):
    pass


class SlotTooSoon(DomainError):
    """Bonus rule: booking requested within the minimum lead time."""


class SlotAlreadyBooked(DomainError):
    pass


class AppointmentAlreadyCancelled(DomainError):
    pass
