from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# --- Auth ---


class UserOut(CamelModel):
    id: UUID
    email: EmailStr
    full_name: str | None = None


class RegisterIn(CamelModel):
    email: EmailStr
    password: str = Field(min_length=4)
    full_name: str | None = None


class LoginIn(CamelModel):
    email: EmailStr
    password: str


class TokenOut(CamelModel):
    token: str
    user: UserOut


# --- KoAP catalogue ---


class KoapArticleOut(CamelModel):
    code: str
    name: str
    weight: int
    factor_group: str


# --- Violation ---


class ViolationOut(CamelModel):
    id: UUID
    article_code: str
    article_name: str
    occurred_at: date
    fine_kzt: int | None = None
    at_fault: bool | None = None
    severity: str  # derived: weight → "Low" | "Medium" | "High" | "Critical"
    factor_group: str


# --- Scoring (used by /drivers and /score/simulate) ---


class ScoreBreakdown(CamelModel):
    speeding: float = 0.0
    harshBraking: float = 0.0
    harshAcceleration: float = 0.0
    phoneUsage: float = 0.0
    redLight: float = 0.0
    accident: float = 0.0


class ScoreResultOut(CamelModel):
    score: int  # safety_score, maps to frontend `score`
    risk_category: str  # 3-cat for frontend RiskBadge
    risk_tier: str  # 5-tier from docx (extra info)
    premium_coefficient: float
    final_premium_kzt: int
    accident_factor: float
    discount: float
    breakdown: dict[str, float]


# --- Drivers ---


class ScoreHistoryPoint(CamelModel):
    period: str  # YYYY-MM
    score: int  # safety_score for that period


class DriverListItem(CamelModel):
    id: str
    full_name: str
    license_number: str
    experience_years: int
    score: int
    risk_category: str
    risk_tier: str
    premium_coefficient: float
    breakdown: dict[str, float]


class DriverDetail(CamelModel):
    id: str
    full_name: str
    license_number: str
    experience_years: int
    city: str
    added_at: datetime
    score_input: dict  # legacy mileage + per-factor counts (computed from violations)
    events: list[dict]  # frontend expects events[]; we re-use violations here
    violations: list[ViolationOut]
    score_history: list[ScoreHistoryPoint]
    # ScoreResult fields flattened (frontend reads them at root)
    score: int
    risk_category: str
    risk_tier: str
    premium_coefficient: float
    final_premium_kzt: int
    accident_factor: float
    discount: float
    breakdown: dict[str, float]


# --- Dashboard ---


class HistogramBucket(CamelModel):
    range: str
    count: int
    band: str


class DashboardSummary(CamelModel):
    total_drivers: int
    average_score: int
    high_risk_share: int  # %
    estimated_loss_ratio: float
    risk_distribution: dict[str, int]  # {low, medium, high}
    score_histogram: list[HistogramBucket]


# --- Simulate ---


class SimulateViolationIn(CamelModel):
    article_code: str
    occurred_at: date
    at_fault: bool = False


class SimulateIn(CamelModel):
    violations: list[SimulateViolationIn]
    accident_count: int = 0
    base_premium: int | None = None


# --- Import ---


class ImportError(CamelModel):
    row: int
    message: str


class ImportResultOut(CamelModel):
    imported_records: int
    recomputed_drivers: int
    errors: list[ImportError] = Field(default_factory=list)
