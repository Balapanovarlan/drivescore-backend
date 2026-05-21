import io

import pytest

from app.koap_catalogue import KOAP_ARTICLES
from app.models import Driver, KoapArticle


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
            full_name="A",
            license_number="KZ-DR-00001",
            experience_years=1,
            city="Astana",
            mileage_km=1000,
        )
    )
    await db_session.commit()


async def test_import_csv_writes_violations_and_recomputes(client, seeded):
    login = await client.post("/auth/register", json={"email": "i@i.i", "password": "testpass1234"})
    token = login.json()["token"]
    csv = (
        "license_number,koap_article,occurred_at,fine_kzt,at_fault\n"
        "KZ-DR-00001,Art.592,2025-01-01,10000,false\n"
        "KZ-DR-00001,Art.599,2025-02-01,20000,false\n"
    )
    resp = await client.post(
        "/import/violations",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("violations.csv", io.BytesIO(csv.encode()), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["importedRecords"] == 2
    assert data["recomputedDrivers"] == 1
    assert data["errors"] == []


async def test_import_csv_unknown_license_returns_error_row(client, seeded):
    login = await client.post("/auth/register", json={"email": "i2@i.i", "password": "testpass1234"})
    token = login.json()["token"]
    csv = (
        "license_number,koap_article,occurred_at,fine_kzt,at_fault\n"
        "KZ-UNKNOWN,Art.592,2025-01-01,10000,false\n"
        "KZ-DR-00001,Art.591,2025-03-01,5000,false\n"
    )
    resp = await client.post(
        "/import/violations",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("violations.csv", io.BytesIO(csv.encode()), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["importedRecords"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 1


async def test_import_csv_semicolon_delimiter(client, seeded):
    """Excel-RU/KZ exports use ';' because comma is the decimal separator."""
    login = await client.post(
        "/auth/register", json={"email": "i3@i.i", "password": "testpass1234"}
    )
    token = login.json()["token"]
    csv = (
        "license_number;koap_article;occurred_at;fine_kzt;at_fault\n"
        "KZ-DR-00001;Art.592;2025-01-01;10000;false\n"
        "KZ-DR-00001;Art.599;2025-02-01;20000;false\n"
    )
    resp = await client.post(
        "/import/violations",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("violations.csv", io.BytesIO(csv.encode()), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["importedRecords"] == 2
    assert data["errors"] == []


async def test_import_csv_missing_required_header_returns_400(client, seeded):
    login = await client.post(
        "/auth/register", json={"email": "i4@i.i", "password": "testpass1234"}
    )
    token = login.json()["token"]
    # No "occurred_at" column
    csv = (
        "license_number,koap_article,fine_kzt\n"
        "KZ-DR-00001,Art.592,10000\n"
    )
    resp = await client.post(
        "/import/violations",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("violations.csv", io.BytesIO(csv.encode()), "text/csv")},
    )
    assert resp.status_code == 400
    assert "occurred_at" in resp.json()["detail"]


async def test_import_csv_bad_date_returns_error_row(client, seeded):
    login = await client.post(
        "/auth/register", json={"email": "i5@i.i", "password": "testpass1234"}
    )
    token = login.json()["token"]
    csv = (
        "license_number,koap_article,occurred_at,fine_kzt,at_fault\n"
        "KZ-DR-00001,Art.592,not-a-date,10000,false\n"
        "KZ-DR-00001,Art.599,2025-02-01,20000,false\n"
    )
    resp = await client.post(
        "/import/violations",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("violations.csv", io.BytesIO(csv.encode()), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["importedRecords"] == 1
    assert len(data["errors"]) == 1
    assert "date" in data["errors"][0]["message"].lower()
