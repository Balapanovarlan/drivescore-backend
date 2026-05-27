from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(...)
    jwt_secret: str = Field(...)
    jwt_algorithm: str = "HS256"
    jwt_expires_days: int = 7
    cors_origins: list[str] | str = Field(default_factory=list)

    # Formula constants from другаяформула.docx (composite UBI/PHYD model)
    base_premium_kzt: int = 22_000
    k_scale: float = 0.07
    k_decay: float = 0.5
    accident_penalty: int = 10

    # Seed
    seed_drivers: int = 100
    seed_rng_seed: int = 42
    seed_test_user_email: str = "info@adam.ua"
    seed_test_user_password: str = "demo"

    # Brute-force protection (per email)
    login_max_attempts: int = 5
    login_window_seconds: int = 900
    login_lockout_seconds: int = 900

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_csv(cls, v: list[str] | str) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Railway / Heroku set DATABASE_URL with the legacy `postgres://` or
        the sync `postgresql://` prefix. We use the async driver everywhere,
        so rewrite to `postgresql+asyncpg://` automatically."""
        if not isinstance(v, str):
            return v
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
