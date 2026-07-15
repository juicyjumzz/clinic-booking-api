"""
Centralised application configuration.

We read everything from environment variables (with sane defaults for local
development) rather than hardcoding values, so the exact same code can run
locally, in CI, and on Render just by changing environment variables.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # SQLAlchemy connection string. Defaults to a local SQLite file so the
    # project runs with zero external setup. On Render we still use SQLite
    # (see README for the trade-offs of that decision), but the value is
    # still read from the environment so it can be swapped without code
    # changes if the project ever moves to Postgres.
    database_url: str = "sqlite:///./clinic.db"

    # IANA timezone the clinic physically operates in. Doctors' working
    # hours (e.g. 09:00-17:00) are defined in *this* timezone. All
    # datetimes are converted to UTC before being stored in the database,
    # and converted back to this timezone whenever we need to compare a
    # datetime against a doctor's working hours.
    clinic_timezone: str = "Africa/Nairobi"

    # Length of a single bookable slot, in minutes. Pulled out as a setting
    # (rather than a magic number scattered through the code) because the
    # brief says the clinic "wants to grow" - a future clinic might use a
    # different slot length.
    slot_minutes: int = 30

    # Bonus requirement: block bookings made less than this many minutes
    # before the slot starts.
    min_lead_time_minutes: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings accessor. FastAPI will call this once per process
    (thanks to lru_cache) instead of re-reading environment variables on
    every request.
    """
    return Settings()
