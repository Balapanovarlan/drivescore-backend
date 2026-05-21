"""Tests for /api/users (admin-only)."""

import pytest

from app.auth import hash_password
from app.models import User


@pytest.fixture
async def admin_token(client, db_session):
    db_session.add(
        User(
            email="boss@example.com",
            full_name="Boss",
            password_hash=hash_password("adminpass"),
            role="admin",
        )
    )
    await db_session.commit()
    resp = await client.post(
        "/auth/login",
        json={"email": "boss@example.com", "password": "adminpass"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


@pytest.fixture
async def manager_token(client, db_session):
    db_session.add(
        User(
            email="staff@example.com",
            full_name="Staff",
            password_hash=hash_password("managerpass"),
            role="manager",
        )
    )
    await db_session.commit()
    resp = await client.post(
        "/auth/login",
        json={"email": "staff@example.com", "password": "managerpass"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


async def test_list_users_requires_admin(client, manager_token):
    resp = await client.get(
        "/users", headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert resp.status_code == 403


async def test_list_users_returns_array_for_admin(client, admin_token):
    resp = await client.get(
        "/users", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(u["email"] == "boss@example.com" for u in data)
    boss = next(u for u in data if u["email"] == "boss@example.com")
    assert boss["role"] == "admin"


async def test_create_user_requires_admin(client, manager_token):
    resp = await client.post(
        "/users",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={
            "email": "new@example.com",
            "password": "newpass",
            "fullName": "New Person",
        },
    )
    assert resp.status_code == 403


async def test_create_user_succeeds_for_admin(client, admin_token):
    resp = await client.post(
        "/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "alice@example.com",
            "password": "alicepass",
            "fullName": "Alice Smith",
        },
    )
    assert resp.status_code == 201
    user = resp.json()
    assert user["email"] == "alice@example.com"
    assert user["fullName"] == "Alice Smith"
    assert user["role"] == "manager"
    # Created user can log in immediately
    login = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "alicepass"},
    )
    assert login.status_code == 200


async def test_create_user_can_grant_admin_role(client, admin_token):
    resp = await client.post(
        "/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "vp@example.com",
            "password": "vppass",
            "fullName": "VP",
            "role": "admin",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "admin"


async def test_create_user_rejects_unknown_role(client, admin_token):
    resp = await client.post(
        "/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "bogus@example.com",
            "password": "bogus",
            "role": "superduper",
        },
    )
    assert resp.status_code == 422


async def test_create_user_rejects_duplicate_email(client, admin_token):
    await client.post(
        "/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "dup@example.com", "password": "dup1234"},
    )
    resp = await client.post(
        "/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "dup@example.com", "password": "dup5678"},
    )
    assert resp.status_code == 409


async def test_create_user_requires_auth(client):
    resp = await client.post(
        "/users",
        json={"email": "x@example.com", "password": "anything"},
    )
    assert resp.status_code == 401
