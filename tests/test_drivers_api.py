from datetime import date

import pytest

from app.koap_catalogue import KOAP_ARTICLES
from app.models import Driver, KoapArticle, Violation


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
    db_session.add(
        Driver(
            id="DR-00001",
            full_name="Aibek Test",
            license_number="KZ-DR-00001",
            experience_years=5,
            city="Astana",
            mileage_km=12000,
        )
    )
    await db_session.commit()
    db_session.add(
        Violation(
            driver_id="DR-00001",
            article_code="Art.592",
            occurred_at=date(2024, 5, 21),
            fine_kzt=10000,
            at_fault=False,
            recurrence_idx=1,
        )
    )
    await db_session.commit()
    return None


async def test_get_koap_articles(client, seeded):
    resp = await client.get("/koap-articles")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 12
    assert any(a["code"] == "Art.591" for a in data)


async def test_list_drivers_returns_scored_items(client, seeded):
    # Auth required → quick login
    login = await client.post("/auth/login", json={"email": "x@x.x", "password": "p"})
    token = login.json()["token"]
    resp = await client.get("/drivers", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["id"] == "DR-00001"
    assert item["fullName"] == "Aibek Test"
    assert 0 <= item["score"] <= 100
    assert item["riskCategory"] in {"low", "medium", "high"}


async def test_get_driver_detail(client, seeded):
    login = await client.post("/auth/login", json={"email": "x@x.x", "password": "p"})
    token = login.json()["token"]
    resp = await client.get("/drivers/DR-00001", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "DR-00001"
    assert "violations" in data and len(data["violations"]) == 1
    assert "scoreHistory" in data
    assert "breakdown" in data


async def test_get_driver_404(client, seeded):
    login = await client.post("/auth/login", json={"email": "x@x.x", "password": "p"})
    token = login.json()["token"]
    resp = await client.get("/drivers/UNKNOWN", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
