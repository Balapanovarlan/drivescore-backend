# DriveScore Backend

FastAPI backend for the **DriveScore** driver-risk scoring app — a B2B portfolio-risk dashboard for Kazakhstani auto insurers.

The scoring engine implements the formula from a thesis spec (`формула.docx`): a weighted-sum risk score across КоАП violations, with recurrence multiplier, time decay, accident factor, and a safe-driving discount. The result maps to one of five tiers and an insurance premium coefficient.

## Stack

Python 3.12, FastAPI, async SQLAlchemy 2 + asyncpg, Alembic, pydantic-settings, PyJWT, bcrypt, python-multipart. Tests use `pytest-asyncio` + `httpx` + in-memory SQLite via `aiosqlite`.

## Layout

```
app/
  main.py          # FastAPI app + lifespan (alembic upgrade + seed)
  config.py        # Settings via env vars
  database.py      # async engine + get_db dep
  models.py        # 5 ORM tables: users, koap_articles, drivers, violations, score_snapshots
  schemas.py       # Pydantic schemas (camelCase aliases for JSON)
  crud.py          # async DB helpers + scoring helpers
  scoring.py       # PURE engine — mirrors формула.docx, no DB imports
  koap_catalogue.py# 12 КоАП articles with weight + factor_group
  auth.py          # bcrypt + JWT + get_current_user dependency
  seed.py          # generates KZ drivers + 6 monthly snapshots
  routers/
    auth_router.py        # /api/auth/{register,login,me}
    drivers_router.py     # /api/drivers, /api/drivers/{id}
    violations_router.py  # /api/koap-articles
    simulate_router.py    # /api/score/simulate
    dashboard_router.py   # /api/dashboard/summary
    import_router.py      # /api/import/violations (multipart CSV)
alembic/             # migrations
tests/               # 45 tests; locked contract tests for the formula
Dockerfile           # python:3.12-slim, runs alembic + uvicorn
```

## Local development (no docker)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL="postgresql+asyncpg://drivescore:drivescore@localhost:5432/drivescore"
export JWT_SECRET="dev-secret-change-me-32chars-minimum"
alembic upgrade head
uvicorn app.main:app --reload
```

## Tests

```bash
pytest -q
```

The two locked contract tests assert that the scoring engine reproduces the two worked examples from the thesis spec (174 556 ₸ and 653 520 ₸).

## Docker (single service)

```bash
docker build -t drivescore-backend .
docker run --rm -e DATABASE_URL=... -e JWT_SECRET=... -p 8000:8000 drivescore-backend
```

## Deployment — Railway

The Dockerfile honours `$PORT`. Add a Postgres add-on; Railway injects `DATABASE_URL`. Set `JWT_SECRET`, `CORS_ORIGINS`, and (optional) `SEED_DRIVERS`. On boot the container runs `alembic upgrade head`, then `uvicorn`. The first boot seeds 100 KZ drivers + 12 КоАП articles + a test user `info@adam.ua`.

## Demo auth

`/api/auth/login` accepts any email and upserts the user on first request — this is an educational demo, not production auth. JWT is HS256, 7-day expiry.
