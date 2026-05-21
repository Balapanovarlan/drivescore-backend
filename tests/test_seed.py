from sqlalchemy import select

from app.models import Driver, KoapArticle, ScoreSnapshot, User, Violation
from app.seed import seed_if_empty


async def test_seed_populates_catalogue_drivers_and_snapshots(db_session, monkeypatch):
    monkeypatch.setenv("SEED_DRIVERS", "10")
    await seed_if_empty(db_session, drivers_count=10)

    articles = list((await db_session.execute(select(KoapArticle))).scalars().all())
    drivers = list((await db_session.execute(select(Driver))).scalars().all())
    violations = list((await db_session.execute(select(Violation))).scalars().all())
    snaps = list((await db_session.execute(select(ScoreSnapshot))).scalars().all())
    users = list((await db_session.execute(select(User))).scalars().all())

    assert len(articles) == 12
    assert len(drivers) == 10
    assert len(violations) >= 10  # at least 1 per driver on average
    assert len(snaps) == 10 * 6  # 6 monthly snapshots per driver
    assert any(u.email == "info@adam.ua" for u in users)


async def test_seed_is_idempotent(db_session):
    await seed_if_empty(db_session, drivers_count=5)
    drivers_before = len((await db_session.execute(select(Driver))).scalars().all())
    await seed_if_empty(db_session, drivers_count=5)
    drivers_after = len((await db_session.execute(select(Driver))).scalars().all())
    assert drivers_before == drivers_after == 5
