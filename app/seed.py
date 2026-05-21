import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hash_password
from app.config import get_settings
from app.koap_catalogue import KOAP_ARTICLES, KOAP_BY_CODE
from app.models import Driver, KoapArticle, ScoreSnapshot, User, Violation
from app.scoring import ViolationRow, compute_score

KZ_FIRST_NAMES = [
    "Aibek",
    "Dana",
    "Marat",
    "Aigul",
    "Nurlan",
    "Aliya",
    "Bekzat",
    "Saltanat",
    "Yerlan",
    "Zhanna",
    "Daulet",
    "Madina",
    "Sanzhar",
    "Aizhan",
    "Talgat",
    "Gulnaz",
    "Kuanysh",
    "Aiym",
    "Ruslan",
    "Symbat",
]
KZ_LAST_NAMES = [
    "Nurlanov",
    "Yerlanqyzy",
    "Saparov",
    "Asanova",
    "Tursynov",
    "Bektenova",
    "Omarov",
    "Zhumagulova",
    "Kassymov",
    "Karimova",
    "Akhmetov",
    "Tleulina",
    "Nazarbayev",
    "Iskakova",
    "Mukhamedjanov",
    "Yusupova",
]
CITIES = [
    "Astana",
    "Almaty",
    "Shymkent",
    "Karaganda",
    "Aktobe",
    "Taraz",
    "Pavlodar",
    "Ust-Kamenogorsk",
    "Semey",
    "Atyrau",
]


def _gen_violations(rng: random.Random, today: date) -> list[dict]:
    n = rng.randint(0, 10)
    rows = []
    # Bias toward minor offences
    bias = ["Art.592"] * 5 + ["Art.591"] * 4 + ["Art.599"] * 3 + ["Art.593"] * 2
    bias += [a["code"] for a in KOAP_ARTICLES]
    for _ in range(n):
        code = rng.choice(bias)
        days_ago = rng.randint(1, 5 * 365)
        rows.append({"code": code, "occurred_at": today - timedelta(days=days_ago)})
    return rows


def _is_at_fault_article(code: str) -> bool:
    accident_codes = {"Art.608 Part 3", "Art.611 Part 2", "Art.608 Part 1"}
    return code in accident_codes


def _compute_snapshot_for_period(violations: list[Violation], period_end: date):
    rows = [
        ViolationRow(
            article_code=v.article_code,
            weight=KOAP_BY_CODE[v.article_code]["weight"],
            occurred_at=v.occurred_at,
            at_fault=bool(v.at_fault),
        )
        for v in violations
        if v.occurred_at <= period_end
    ]
    accident_count = sum(1 for v in violations if v.at_fault and v.occurred_at <= period_end)
    return compute_score(rows, accident_count, period_end)


async def seed_if_empty(db: AsyncSession, drivers_count: int | None = None) -> None:
    settings = get_settings()
    drivers_count = drivers_count if drivers_count is not None else settings.seed_drivers
    rng = random.Random(settings.seed_rng_seed)

    # Catalogue
    existing_articles = await db.execute(select(KoapArticle))
    if not list(existing_articles.scalars().all()):
        db.add_all(
            [
                KoapArticle(
                    code=a["code"],
                    name=a["name"],
                    weight=a["weight"],
                    factor_group=a["factor_group"],
                )
                for a in KOAP_ARTICLES
            ]
        )
        await db.commit()

    # Test user
    existing_user = await db.execute(
        select(User).where(User.email == settings.seed_test_user_email)
    )
    if existing_user.scalar_one_or_none() is None:
        db.add(
            User(
                email=settings.seed_test_user_email,
                full_name="Test User",
                password_hash=hash_password(settings.seed_test_user_password),
            )
        )
        await db.commit()

    # Drivers
    existing_drivers = await db.execute(select(Driver))
    if list(existing_drivers.scalars().all()):
        return  # already seeded

    today = date.today()
    for i in range(1, drivers_count + 1):
        first = rng.choice(KZ_FIRST_NAMES)
        last = rng.choice(KZ_LAST_NAMES)
        driver = Driver(
            id=f"DR-{i:05d}",
            full_name=f"{first} {last}",
            license_number=f"KZ-DR-{i:05d}",
            experience_years=rng.randint(1, 25),
            city=rng.choice(CITIES),
            mileage_km=rng.randint(5_000, 35_000),
        )
        db.add(driver)
        await db.flush()

        violations: list[Violation] = []
        per_article_counter: dict[str, int] = {}
        for v in _gen_violations(rng, today):
            code = v["code"]
            per_article_counter[code] = per_article_counter.get(code, 0) + 1
            at_fault = _is_at_fault_article(code) and rng.random() < 0.5
            violation = Violation(
                driver_id=driver.id,
                article_code=code,
                occurred_at=v["occurred_at"],
                fine_kzt=rng.choice([5000, 10_000, 15_000, 25_000, 50_000]),
                at_fault=at_fault,
                recurrence_idx=per_article_counter[code],
            )
            db.add(violation)
            violations.append(violation)
        await db.flush()

        # Six monthly snapshots: current month and 5 prior
        for months_back in range(5, -1, -1):
            y = today.year
            m = today.month - months_back
            while m <= 0:
                m += 12
                y -= 1
            period_end = date(y, m, 28)
            period = f"{y:04d}-{m:02d}"
            result = _compute_snapshot_for_period(violations, period_end)
            db.add(
                ScoreSnapshot(
                    driver_id=driver.id,
                    period=period,
                    risk_score=result.risk_score,
                    safety_score=result.safety_score,
                    risk_tier=result.risk_tier,
                    premium_coef=result.premium_coefficient,
                )
            )

        await db.commit()
