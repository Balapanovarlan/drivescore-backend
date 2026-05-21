import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Driver, KoapArticle, ScoreSnapshot, User, Violation


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as s:
        yield s


async def test_create_user_driver_violation(session: AsyncSession):
    from datetime import date

    user = User(email="a@b.c", full_name="A B", password_hash="h")
    article = KoapArticle(code="Art.591", name="Phone", weight=5, factor_group="phoneUsage")
    driver = Driver(
        id="DR-00001",
        full_name="Test Driver",
        license_number="KZ-DR-00001",
        experience_years=5,
        city="Astana",
        mileage_km=12000,
    )
    session.add_all([user, article, driver])
    await session.flush()
    v = Violation(
        driver_id=driver.id,
        article_code=article.code,
        occurred_at=date(2024, 5, 1),
        fine_kzt=10000,
        at_fault=False,
        recurrence_idx=1,
    )
    snap = ScoreSnapshot(
        driver_id=driver.id,
        period="2026-05",
        risk_score=12.5,
        safety_score=66,
        risk_tier="moderate",
        premium_coef=1.0,
    )
    session.add_all([v, snap])
    await session.commit()
    assert v.id is not None
    assert snap.id is not None
