"""
Application entrypoint. Wires together the routers, creates database
tables on startup, and exposes a health check for deployment monitoring.

Table creation: for a project this size we use SQLAlchemy's
Base.metadata.create_all() on startup rather than a migrations tool like
Alembic. This is a deliberate scope decision, documented in the README:
Alembic is the right tool once a schema needs to evolve across
environments with real historical data, but for a fresh take-home project
with no production data yet, it would add ceremony without adding safety.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import appointments, doctors, patients
from app.core.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Clinic Booking API",
    description="A REST API for booking, cancelling, and rescheduling doctor appointments.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(doctors.router)
app.include_router(appointments.router)
app.include_router(patients.router)


@app.get("/health", tags=["health"])
def health_check():
    """Used by Render (and any future load balancer/uptime monitor) to
    confirm the process is alive and serving requests."""
    return {"status": "ok"}
