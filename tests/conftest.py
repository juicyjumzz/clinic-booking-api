"""
Shared test fixtures.

Each test gets its own fresh SQLite file-based database (a temp file, not
:memory:, because the race-condition test spins up multiple real threads,
each needing its own connection to the *same* database - SQLite's
":memory:" database is private per-connection unless special shared-cache
flags are used, which real file-backed SQLite avoids entirely). Every test
starts from a clean slate and seeds its own doctors, so tests never leak
state into one another.
"""

import os
import tempfile
from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app
from app.models.doctor import Doctor


@pytest.fixture()
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.remove(path)


@pytest.fixture()
def engine(db_path):
    eng = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture()
def TestingSessionLocal(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def client(engine, TestingSessionLocal):
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def future_slot_iso(days_ahead: int = 30, hour: int = 10, minute: int = 0) -> str:
    """
    Build an ISO 8601 datetime string, `days_ahead` days from today, at the
    given local (Africa/Nairobi) clock time. Nairobi does not observe
    daylight saving time, so its UTC offset is a constant +03:00 year
    round, which makes it safe to hardcode here.

    Computed relative to "today" (rather than a fixed calendar date) so
    these tests never go stale / start failing the "slot in the past"
    check just because time has passed since this file was written.
    """
    from datetime import datetime, timedelta

    target_date = (datetime.now() + timedelta(days=days_ahead)).date()
    return f"{target_date.isoformat()}T{hour:02d}:{minute:02d}:00+03:00"


@pytest.fixture()
def seeded_doctor(TestingSessionLocal):
    """Doctor working 09:00-17:00 Africa/Nairobi, matching the scenario."""
    db = TestingSessionLocal()
    doctor = Doctor(
        full_name="Dr. Test Subject",
        specialty="General Practice",
        work_start=time(9, 0),
        work_end=time(17, 0),
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    doctor_id = doctor.id
    db.close()
    return doctor_id
