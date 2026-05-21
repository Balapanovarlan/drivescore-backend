import pytest

from app.koap_catalogue import KOAP_ARTICLES
from app.models import KoapArticle


@pytest.fixture
async def with_articles(db_session):
    db_session.add_all(
        [
            KoapArticle(
                code=a["code"], name=a["name"], weight=a["weight"], factor_group=a["factor_group"]
            )
            for a in KOAP_ARTICLES
        ]
    )
    await db_session.commit()


async def test_simulate_returns_score_and_premium(client, with_articles):
    login = await client.post("/auth/login", json={"email": "s@s.s", "password": "p"})
    token = login.json()["token"]
    resp = await client.post(
        "/score/simulate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "violations": [
                {"articleCode": "Art.592", "occurredAt": "2024-05-21", "atFault": False}
            ],
            "accidentCount": 0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert data["riskCategory"] in {"low", "medium", "high"}
    assert "finalPremiumKzt" in data


async def test_simulate_unknown_article_returns_422(client, with_articles):
    login = await client.post("/auth/login", json={"email": "s2@s.s", "password": "p"})
    token = login.json()["token"]
    resp = await client.post(
        "/score/simulate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "violations": [
                {"articleCode": "Art.NONEXISTENT", "occurredAt": "2024-05-21", "atFault": False}
            ],
            "accidentCount": 0,
        },
    )
    assert resp.status_code == 422
