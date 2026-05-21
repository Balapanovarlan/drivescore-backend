import pytest

from app.koap_catalogue import KOAP_ARTICLES
from app.models import Driver, KoapArticle, ScoreSnapshot


@pytest.fixture
async def seeded(db_session):
    db_session.add_all(
        [
            KoapArticle(
                code=a["code"], name=a["name"], weight=a["weight"], factor_group=a["factor_group"]
            )
            for a in KOAP_ARTICLES
        ]
    )
    drivers = [
        Driver(
            id=f"DR-{i:05d}",
            full_name=f"Driver {i}",
            license_number=f"KZ-DR-{i:05d}",
            experience_years=i,
            city="Astana",
            mileage_km=10000,
        )
        for i in range(1, 6)
    ]
    db_session.add_all(drivers)
    await db_session.commit()
    snaps = [
        ScoreSnapshot(
            driver_id="DR-00001",
            period="2026-05",
            risk_score=0.0,
            safety_score=100,
            risk_tier="low",
            premium_coef=0.9,
        ),
        ScoreSnapshot(
            driver_id="DR-00002",
            period="2026-05",
            risk_score=10.0,
            safety_score=72,
            risk_tier="moderate",
            premium_coef=1.0,
        ),
        ScoreSnapshot(
            driver_id="DR-00003",
            period="2026-05",
            risk_score=25.0,
            safety_score=43,
            risk_tier="high",
            premium_coef=1.3,
        ),
        ScoreSnapshot(
            driver_id="DR-00004",
            period="2026-05",
            risk_score=40.0,
            safety_score=26,
            risk_tier="dangerous",
            premium_coef=1.7,
        ),
        ScoreSnapshot(
            driver_id="DR-00005",
            period="2026-05",
            risk_score=70.0,
            safety_score=10,
            risk_tier="critical",
            premium_coef=2.2,
        ),
    ]
    db_session.add_all(snaps)
    await db_session.commit()


async def test_dashboard_summary(client, seeded):
    login = await client.post("/auth/login", json={"email": "d@d.d", "password": "p"})
    token = login.json()["token"]
    resp = await client.get("/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["totalDrivers"] == 5
    assert 0 <= data["averageScore"] <= 100
    assert "riskDistribution" in data
    assert set(data["riskDistribution"].keys()) == {"low", "medium", "high"}
    assert isinstance(data["scoreHistogram"], list)
    assert len(data["scoreHistogram"]) == 10
