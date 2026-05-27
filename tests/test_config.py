from app.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost,http://example.com")
    s = Settings()
    assert s.database_url == "postgresql+asyncpg://u:p@h:5432/d"
    assert s.jwt_secret == "test-secret"
    assert s.cors_origins == ["http://localhost", "http://example.com"]


def test_settings_defaults_for_constants(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "x")
    s = Settings()
    assert s.base_premium_kzt == 22_000
    assert s.k_scale == 0.07
    assert s.k_decay == 0.5
    assert s.accident_penalty == 10
    assert s.seed_drivers == 100
    assert s.jwt_expires_days == 7
