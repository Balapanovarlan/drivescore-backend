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


async def test_login_succeeds_with_correct_password(client):
    await client.post(
        "/auth/register",
        json={"email": "ok@example.com", "password": "rightpass"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "ok@example.com", "password": "rightpass"},
    )
    assert resp.status_code == 200
    assert "token" in resp.json()


async def test_login_wrong_password_returns_401(client):
    await client.post(
        "/auth/register",
        json={"email": "wrong@example.com", "password": "correct123"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "wrong@example.com", "password": "incorrect"},
    )
    assert resp.status_code == 401


async def test_login_unknown_email_returns_401(client):
    resp = await client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "whatever"},
    )
    assert resp.status_code == 401


async def test_login_email_case_insensitive_for_throttling(client):
    """Failed attempts on Foo@Example.com count toward foo@example.com lockout."""
    for _ in range(5):
        await client.post(
            "/auth/login",
            json={"email": "Mixed@Example.COM", "password": "x"},
        )
    resp = await client.post(
        "/auth/login",
        json={"email": "mixed@example.com", "password": "x"},
    )
    assert resp.status_code == 429


async def test_login_locks_after_5_failures(client):
    await client.post(
        "/auth/register",
        json={"email": "lock@example.com", "password": "correctpw"},
    )
    for i in range(5):
        resp = await client.post(
            "/auth/login",
            json={"email": "lock@example.com", "password": "wrong"},
        )
        if i < 4:
            assert resp.status_code == 401, f"attempt {i + 1} should still be 401"
        else:
            assert resp.status_code == 429
            assert "Retry-After" in resp.headers
    # Even the correct password should now be rejected until lockout expires
    resp = await client.post(
        "/auth/login",
        json={"email": "lock@example.com", "password": "correctpw"},
    )
    assert resp.status_code == 429


async def test_successful_login_resets_failure_counter(client):
    await client.post(
        "/auth/register",
        json={"email": "reset@example.com", "password": "correctpw"},
    )
    for _ in range(4):
        await client.post(
            "/auth/login",
            json={"email": "reset@example.com", "password": "wrong"},
        )
    resp = await client.post(
        "/auth/login",
        json={"email": "reset@example.com", "password": "correctpw"},
    )
    assert resp.status_code == 200
    for _ in range(4):
        resp = await client.post(
            "/auth/login",
            json={"email": "reset@example.com", "password": "wrong"},
        )
        assert resp.status_code == 401


async def test_me_returns_current_user(client):
    reg = await client.post(
        "/auth/register",
        json={"email": "me@example.com", "password": "mepass1234"},
    )
    token = reg.json()["token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"
