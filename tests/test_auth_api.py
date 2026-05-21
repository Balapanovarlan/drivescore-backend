async def test_login_upserts_new_user_demo_mode(client):
    resp = await client.post(
        "/auth/login",
        json={"email": "new@example.com", "password": "anything"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["email"] == "new@example.com"


async def test_login_existing_user_wrong_password_still_succeeds_demo(client):
    # Demo upsert mode: if email exists, the password is ignored on login
    # (since the user was likely created by an earlier demo session).
    await client.post(
        "/auth/login",
        json={"email": "x@y.z", "password": "first"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "x@y.z", "password": "different"},
    )
    assert resp.status_code == 200


async def test_register_creates_user(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "reg@example.com", "password": "pw1234", "fullName": "Test"},
    )
    assert resp.status_code == 201
    assert resp.json()["user"]["email"] == "reg@example.com"


async def test_register_duplicate_returns_409(client):
    await client.post(
        "/auth/register",
        json={"email": "dup@example.com", "password": "pw1234"},
    )
    resp = await client.post(
        "/auth/register",
        json={"email": "dup@example.com", "password": "pw1234"},
    )
    assert resp.status_code == 409


async def test_me_returns_current_user(client):
    login = await client.post(
        "/auth/login",
        json={"email": "me@example.com", "password": "x"},
    )
    token = login.json()["token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"
