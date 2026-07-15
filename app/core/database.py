"""
Database engine and session management.

We use SQLAlchemy 2.0's ORM. A single Engine is created for the lifetime of
the process, and each request gets its own Session via the get_db
dependency below, which is closed automatically when the request finishes.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# check_same_thread=False is required for SQLite when it's accessed from
# multiple threads, which is how FastAPI/uvicorn serves requests. This is
# safe here because SQLAlchemy's connection pool still hands each request
# its own connection.
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """
    SQLite does not enforce FOREIGN KEY constraints unless you turn them on
    for every connection. Without this, a bad doctor_id could silently be
    inserted into appointments.
    """
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base class for all ORM models."""

    pass


def get_db():
    """
    FastAPI dependency that yields a database session for the duration of
    a single request, and guarantees it is closed afterwards even if the
    request raises an exception.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
