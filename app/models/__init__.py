"""
Importing this package guarantees both Doctor and Appointment are
registered with SQLAlchemy's mapper registry together, since Doctor's
relationship to Appointment (and vice versa) is declared by class name as
a string and needs both classes loaded to resolve correctly.
"""

from app.models.appointment import Appointment  # noqa: F401
from app.models.doctor import Doctor  # noqa: F401

__all__ = ["Doctor", "Appointment"]
