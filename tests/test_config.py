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
    assert s.base_premium_kzt == 200_000
    assert s.alpha == 0.02
    assert s.k_decay == 0.2
    assert s.seed_drivers == 100
    assert s.jwt_expires_days == 7
