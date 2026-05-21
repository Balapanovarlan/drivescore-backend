"""
Shared test fixtures: env defaults, in-memory sqlite DB per test, httpx async client.
"""

import os

# Set env BEFORE any `app.*` import so `app.config` finds the values.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-32chars-minimum-padding-here")
os.environ.setdefault("CORS_ORIGINS", "http://localhost")

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.security import login_throttler


@pytest.fixture(autouse=True)
def _reset_throttler():
    """Throttler is process-global; reset it between tests so lockouts don't leak."""
    login_throttler.reset()
    yield
    login_throttler.reset()


@pytest.fixture
async def db_session() -> AsyncIterator:
    # Import app (and thus all models) before create_all so Base.metadata is fully populated.
    from app.main import app  # noqa: F401 — side-effect: registers models with Base.metadata

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async def _override() -> AsyncIterator:
        async with SessionLocal() as s:
            yield s

    app.dependency_overrides[get_db] = _override
    async with SessionLocal() as session:
        yield session
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api") as ac:
        yield ac


@pytest.fixture
async def auth_client(client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """Registers a fresh user and returns a client with that JWT attached."""
    resp = await client.post(
        "/auth/register",
        json={"email": "fixture@drivescore.test", "password": "fixturepass"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    yield client
