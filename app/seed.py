"""
Seed the database with the 5 doctors described in the assessment scenario.

Run with:  python -m app.seed

Safe to re-run: it checks whether doctors already exist before inserting,
so it won't create duplicates if you run it more than once.
"""

from datetime import time

from app.core.database import Base, SessionLocal, engine
from app.models.doctor import Doctor

SEED_DOCTORS = [
    {"full_name": "Dr. Amina Yusuf", "specialty": "General Practice", "work_start": time(9, 0), "work_end": time(17, 0)},
    {"full_name": "Dr. Brian Otieno", "specialty": "Paediatrics", "work_start": time(8, 0), "work_end": time(16, 0)},
    {"full_name": "Dr. Grace Wanjiru", "specialty": "Dermatology", "work_start": time(10, 0), "work_end": time(18, 0)},
    {"full_name": "Dr. Kevin Mwangi", "specialty": "General Practice", "work_start": time(9, 0), "work_end": time(13, 0)},
    {"full_name": "Dr. Faith Njoki", "specialty": "Gynaecology", "work_start": time(11, 0), "work_end": time(19, 0)},
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing_count = db.query(Doctor).count()
        if existing_count > 0:
            print(f"Doctors table already has {existing_count} row(s); skipping seed.")
            return
        for doc in SEED_DOCTORS:
            db.add(Doctor(**doc))
        db.commit()
        print(f"Seeded {len(SEED_DOCTORS)} doctors.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
