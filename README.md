# Clinic Booking API

A REST API for a small clinic (5 doctors) to let patients check availability,
book, cancel, and reschedule appointments in 30-minute slots.

Built with **FastAPI**, **SQLAlchemy 2.0**, and **SQLite**, deployed on **Render**.

---

## Section 1 — System Design

### Models

**Doctor**
- `id`, `full_name`, `specialty`
- `work_start`, `work_end` — plain clock times (e.g. `09:00`), interpreted in
  the clinic's local timezone (`Africa/Nairobi`, configurable).

Deliberately excludes personal contact details (phone, personal email). A
public booking API has no reason to expose a doctor's private contact
information to anyone who calls `GET /doctors/{id}/availability`.

**Appointment**
- `id`, `doctor_id` (FK), `patient_id` (plain integer — see "Assumptions" below)
- `slot_start`, `slot_end` — always UTC
- `status` — `booked` or `cancelled`
- `cancellation_reason`, `created_at`, `updated_at`

There is no separate `Patient` model. The brief only ever refers to a
`patient_id`; inventing a `Patient` table with unspecified fields (name?
email? phone?) would be adding scope the brief doesn't ask for. If patient
identity, authentication, or contact details become a requirement, this is
the natural extension point.

### Key Decisions

**Slots are a fixed grid, not flexible ranges.** Every doctor's working day
is divided into fixed 30-minute boundaries starting at `work_start` (e.g.
09:00, 09:30, 10:00...). A slot is identified by `(doctor_id, slot_start)`.
This is simpler and far less error-prone than "flexible" slots that could
start at any minute, at the cost of not supporting variable-length
appointments (e.g. a 45-minute consultation) without further work.

**All datetimes are stored and reasoned about in UTC.** Doctors' working
hours are defined as clock times in the clinic's local timezone (because
"9am" is what a receptionist types in), but every appointment `slot_start`
in the database is UTC. This avoids the classic bug where "9am" silently
means different things depending on server timezone or daylight saving.
Note: SQLite has no native timezone-aware datetime type, so values are
stored *naive* but the whole codebase treats naive datetimes in the
database as implicitly UTC (see `app/core/time_utils.py` for the
conversion boundary — this is documented in code comments at the exact
point it matters, since it's a real footgun if forgotten).

**Concurrency is enforced by the database, not application code.** This is
the most important decision in the project. A naive implementation checks
"is this slot free?" and then inserts — but under concurrent requests, two
checks can both pass before either insert happens, and both bookings
succeed. We instead put a **partial unique index** on
`(doctor_id, slot_start) WHERE status = 'booked'` and always attempt the
write directly, catching the resulting `IntegrityError` if someone beat us
to it. This closes the race condition completely, regardless of timing,
because the database — not application code — is the single source of
truth for "is this slot taken", and the uniqueness check and the write
happen as one atomic operation.

Because the index only covers `status = 'booked'` rows, a cancelled
appointment automatically stops occupying its slot (the row still exists
for history, but the constraint ignores it) — so a slot becomes rebookable
the instant it's cancelled, with no extra cleanup step.

**Rescheduling is a single atomic UPDATE, not cancel-then-rebook.** If we
cancelled the old appointment and then tried to insert a new one as two
separate steps, a patient could lose their original slot if the new one
turned out to be taken in between. Instead, `PATCH .../reschedule` updates
`slot_start`/`slot_end` on the *same row* inside one transaction. If the
new slot is taken, the UPDATE violates the same partial unique index, the
whole transaction rolls back, and the original appointment is completely
untouched. This is covered by an explicit test
(`test_reschedule_onto_taken_slot_returns_409_and_keeps_original`).

**Validation failures use specific HTTP status codes:**
| Situation | Status |
|---|---|
| Doctor / appointment doesn't exist | 404 |
| Slot in the past, outside working hours, off the 30-min grid, or within the minimum lead time | 400 |
| Slot already booked (lost the race, or reschedule target taken) | 409 |
| Appointment already cancelled (on cancel or reschedule) | 409 |
| Malformed request body (e.g. no timezone on the datetime) | 422 (FastAPI/Pydantic default) |

### Assumptions & Trade-offs (documented per the brief's instruction to
note ambiguous calls)

- **Database:** SQLite, for a zero-setup, single-file, take-home-appropriate
  choice. Trade-off: Render's free-tier filesystem is ephemeral, so the
  database resets on every redeploy/restart — acceptable for a
  demonstration project, but a real production deployment of this design
  would use Postgres (the code is written against the SQLAlchemy ORM, not
  raw SQLite, specifically to make that swap low-friction later — the only
  concurrency-critical piece that's SQLite-specific is the choice to use a
  partial unique index + catch-IntegrityError instead of
  `SELECT ... FOR UPDATE`, since SQLite doesn't support real row locking;
  Postgres would let you use either approach).
- **No authentication.** Out of scope per the brief's endpoint list, but a
  known gap: right now any caller can book, cancel, or reschedule on behalf
  of any `patient_id`. In production this needs a real auth layer (e.g. JWT)
  so a patient can only act on their own appointments.
- **No Alembic migrations.** Tables are created via
  `Base.metadata.create_all()` on startup. This is a deliberate scope
  decision — Alembic earns its keep once a schema needs to evolve against
  real historical data across environments; for a fresh project with no
  production data yet, it adds ceremony without adding safety.
- **Doctor's working-hours changes / doctor cancelling a whole day** aren't
  implemented (not required by the brief). Worth naming as a known gap:
  changing a doctor's `work_start`/`work_end` today would not retroactively
  affect already-booked appointments outside the new hours — nothing in the
  current design cascades that change, and it would need explicit handling
  (e.g. flagging conflicting appointments for staff review rather than
  silently cancelling patients' bookings).

---

## Section 2 — Running Locally

### Prerequisites
- Python 3.12
- Git

### Setup

```bash
git clone <your-repo-url>
cd clinic-booking-api
python -m venv .venv
```

Windows (PowerShell):
```powershell
.venv\Scripts\Activate.ps1
```
macOS/Linux:
```bash
source .venv/bin/activate
```

Then:
```bash
pip install -r requirements-dev.txt
python -m app.seed
uvicorn app.main:app --reload
```

The API is now running at `http://127.0.0.1:8000`. Interactive Swagger docs
are at `http://127.0.0.1:8000/docs`.

### Running with Docker

```bash
docker build -t clinic-booking-api .
docker run -p 8000:8000 clinic-booking-api
```

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/appointments` | Book a slot |
| `GET` | `/doctors/{id}/availability?date=YYYY-MM-DD` | List free slots for a doctor on a date |
| `PATCH` | `/appointments/{id}/cancel` | Cancel an appointment (`{"reason": "..."}`) |
| `PATCH` | `/appointments/{id}/reschedule` | Move to a new slot (`{"new_slot_start": "..."}`) |
| `GET` | `/patients/{id}/appointments` | Bonus: upcoming appointments, sorted by date |
| `GET` | `/doctors` | List all doctors (not required, useful for exploring the API) |
| `GET` | `/health` | Health check, used by Render |

`slot_start` / `new_slot_start` must be ISO 8601 datetimes **with a
timezone offset**, e.g. `2026-08-01T09:00:00+03:00` or the UTC-equivalent
`2026-08-01T06:00:00Z`.

### Tests

```bash
pytest -v
```

20 tests covering: valid bookings, double-booking rejection, working-hours
validation, off-grid-time validation, past-slot rejection, the bonus
minimum-lead-time rule, doctor-not-found, cancel + double-cancel, reschedule
+ atomicity-on-conflict, cancelled-appointment reschedule rejection,
availability calculation (including slots freeing up after cancellation),
and — most importantly — a real multi-threaded concurrency test
(`tests/test_concurrency.py`) that fires 12 simultaneous booking requests
at the same slot and asserts exactly one succeeds.

---

## Section 3 — Deployment & CI/CD

**Live URL:** `https://clinic-booking-api-giwq.onrender.com/`

### Deploying to Render

1. Push this repo to GitHub.
2. On [render.com](https://render.com), click **New > Blueprint**, connect
   your GitHub account, and select this repo. Render will detect
   `render.yaml` and configure the service automatically (Docker runtime,
   health check path, environment variables).
3. Click **Apply** / **Create Web Service**. Wait for the first build+deploy
   to finish, then copy the public URL Render assigns
   (`https://clinic-booking-api-giwq.onrender.com/`) into this README.
4. In the Render dashboard for this service, go to **Settings > Deploy
   Hook**, copy the deploy hook URL, and add it to your GitHub repo as a
   secret named `RENDER_DEPLOY_HOOK_URL`
   (**Settings > Secrets and variables > Actions > New repository secret**).
   This is what lets GitHub Actions trigger a Render deploy after tests pass.

### CI/CD Pipeline (`.github/workflows/ci.yml`)

- **On every pull request into `main`:** runs the full `pytest` suite.
  GitHub blocks merging if this fails (enable this via **Settings > Branches
  > Branch protection rules** on `main` → require the `test` status check).
- **On every push to `main`** (i.e. the moment a PR is merged): re-runs
  tests, and — only if they pass — calls the Render deploy hook, which
  triggers a fresh build and deploy of the latest `main`.
- **Designated branch:** `main`. Deploys are triggered only from pushes to
  `main`, never from feature branches or PRs directly.

---

## Section 4 — AI Reflection

1. **What did I use AI for across the four sections?**
   Scaffolding the project structure (models/schemas/services/api split),
   generating boilerplate (Pydantic schemas, FastAPI routers, Dockerfile,
   GitHub Actions YAML), and writing the initial test suite. The core
   design decisions — the fixed slot grid, the partial-unique-index
   concurrency approach, and the atomic-reschedule strategy — were
   directed decisions I made and had the AI implement and verify, not
   things I asked it to decide for me.

2. **One example where an AI suggestion improved the work:**
   I asked it to implement slot booking with concurrency safety, and it
   proposed the partial unique index (`WHERE status = 'booked'`) instead of
   a plain unique constraint on `(doctor_id, slot_start)`. A plain unique
   constraint would have made cancelled slots permanently unbookable
   (since the row still exists), which I hadn't considered until it was
   pointed out — the partial index elegantly solves both the race
   condition *and* the "slot becomes available again after cancellation"
   requirement with one mechanism.

3. **One example where AI output was wrong and how I caught it:**
   The first version of the availability calculation compared
   timezone-aware slot-grid datetimes against timezone-naive datetimes read
   back from SQLite (SQLite silently drops tzinfo on read, even when the
   column is declared `DateTime(timezone=True)`). Booked slots never
   actually disappeared from the availability list — the comparison always
   evaluated to "not equal" even for the same instant. I caught it by
   actually running the test suite end-to-end rather than trusting that
   generated code was correct: `test_booked_slot_disappears_from_availability`
   failed, which pointed straight at the mismatch. The fix was to
   standardize on naive-but-always-UTC datetimes at the storage layer, with
   explicit conversion functions (`to_naive_utc`, `naive_utc_now`) at the
   boundary — documented in code so the next person doesn't reintroduce the
   same bug.

4. **Two decisions I made without AI:**
   - *(Fill in with your own reasoning — e.g. why SQLite over Postgres for
     this specific take-home, or why you chose FastAPI over Django REST
     Framework / Go.)*
   - *(Fill in a second one — e.g. a scope decision about what NOT to build:
     no Patient model, no auth, no Alembic — and why you judged that the
     right call given the brief's actual requirements vs. gold-plating.)*

   *(This section should reflect your actual judgment calls, not mine —
   the assessment specifically wants to see where you trusted your own
   reasoning over AI output.)*
