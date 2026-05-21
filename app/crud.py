from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.koap_catalogue import KOAP_BY_CODE
from app.models import Driver, KoapArticle, ScoreSnapshot, User, Violation
from app.scoring import ViolationRow, compute_score

# --- Users ---


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    res = await db.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    password_hash: str,
    full_name: str | None,
    role: str = "manager",
) -> User:
    user = User(email=email, password_hash=password_hash, full_name=full_name, role=role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def list_users(db: AsyncSession) -> list[User]:
    res = await db.execute(select(User).order_by(User.created_at))
    return list(res.scalars().all())


# --- KoAP catalogue ---


async def list_koap_articles(db: AsyncSession) -> list[KoapArticle]:
    res = await db.execute(select(KoapArticle).order_by(KoapArticle.weight.desc()))
    return list(res.scalars().all())


# --- Drivers ---


async def list_drivers(db: AsyncSession) -> list[Driver]:
    res = await db.execute(select(Driver).order_by(Driver.id))
    return list(res.scalars().all())


async def get_driver(db: AsyncSession, driver_id: str) -> Driver | None:
    res = await db.execute(select(Driver).where(Driver.id == driver_id))
    return res.scalar_one_or_none()


async def get_driver_violations(db: AsyncSession, driver_id: str) -> list[Violation]:
    res = await db.execute(
        select(Violation)
        .where(Violation.driver_id == driver_id)
        .order_by(Violation.occurred_at.desc())
    )
    return list(res.scalars().all())


async def get_driver_snapshots(db: AsyncSession, driver_id: str) -> list[ScoreSnapshot]:
    res = await db.execute(
        select(ScoreSnapshot)
        .where(ScoreSnapshot.driver_id == driver_id)
        .order_by(ScoreSnapshot.period.asc())
    )
    return list(res.scalars().all())


# --- Scoring helpers ---


def violations_to_rows(violations: list[Violation]) -> list[ViolationRow]:
    rows: list[ViolationRow] = []
    for v in violations:
        article = KOAP_BY_CODE.get(v.article_code)
        if article is None:
            continue
        rows.append(
            ViolationRow(
                article_code=v.article_code,
                weight=article["weight"],
                occurred_at=v.occurred_at,
                at_fault=bool(v.at_fault),
            )
        )
    return rows


def count_accidents(violations: list[Violation]) -> int:
    return sum(1 for v in violations if v.at_fault)


def aggregate_breakdown(components: list[dict]) -> dict[str, float]:
    """Map article-level components to the 6 frontend factor groups."""
    out = {
        "speeding": 0.0,
        "harshBraking": 0.0,
        "harshAcceleration": 0.0,
        "phoneUsage": 0.0,
        "redLight": 0.0,
        "accident": 0.0,
    }
    for c in components:
        article = KOAP_BY_CODE.get(c["article_code"])
        if article is None:
            continue
        out[article["factor_group"]] += float(c["contribution"])
    return {k: round(v, 2) for k, v in out.items()}


async def compute_driver_score(db: AsyncSession, driver_id: str, today: date):
    violations = await get_driver_violations(db, driver_id)
    rows = violations_to_rows(violations)
    result = compute_score(rows, accident_count=count_accidents(violations), today=today)
    breakdown = aggregate_breakdown(result.components)
    return violations, result, breakdown


# --- Snapshots ---


async def upsert_snapshot(
    db: AsyncSession,
    driver_id: str,
    period: str,
    risk_score: float,
    safety_score: int,
    risk_tier: str,
    premium_coef: float,
) -> None:
    res = await db.execute(
        select(ScoreSnapshot).where(
            ScoreSnapshot.driver_id == driver_id, ScoreSnapshot.period == period
        )
    )
    snap = res.scalar_one_or_none()
    if snap is None:
        snap = ScoreSnapshot(
            driver_id=driver_id,
            period=period,
            risk_score=risk_score,
            safety_score=safety_score,
            risk_tier=risk_tier,
            premium_coef=premium_coef,
        )
        db.add(snap)
    else:
        snap.risk_score = risk_score
        snap.safety_score = safety_score
        snap.risk_tier = risk_tier
        snap.premium_coef = premium_coef
    await db.commit()


# --- Dashboard ---


async def dashboard_aggregates(db: AsyncSession) -> dict:
    total = (await db.execute(select(func.count(Driver.id)))).scalar() or 0
    # Latest snapshot per driver, identified by max(period) per driver_id
    latest_period_subq = (
        select(ScoreSnapshot.driver_id, func.max(ScoreSnapshot.period).label("period"))
        .group_by(ScoreSnapshot.driver_id)
        .subquery()
    )
    latest_snaps_q = select(ScoreSnapshot).join(
        latest_period_subq,
        (ScoreSnapshot.driver_id == latest_period_subq.c.driver_id)
        & (ScoreSnapshot.period == latest_period_subq.c.period),
    )
    snaps = list((await db.execute(latest_snaps_q)).scalars().all())
    return {"total": total, "latest_snaps": snaps}
