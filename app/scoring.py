"""
Pure scoring engine — mirrors формула.docx exactly.

No database imports. Inputs are plain dataclasses; outputs are plain dataclasses.
Used by /drivers/{id}, /score/simulate, seed, and snapshot recomputation.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import TypedDict

# These constants mirror the same fields in app.config.Settings
# (base_premium_kzt, alpha, k_decay).  When the router calls compute_score it
# passes settings.base_premium_kzt as base_premium; these module-level values
# are the spec-locked defaults and the test contract.
ALPHA = 0.02
K_DECAY = 0.2
BASE_PREMIUM_KZT = 200_000

# (upper-bound inclusive, tier name, premium coefficient).
# Lookup picks the first tier whose upper bound >= score, so fractional
# scores like 5.2 fall into "moderate" (between the integer band 5 and 15).
TIERS = [
    (5, "low", 0.9),
    (15, "moderate", 1.0),
    (30, "high", 1.3),
    (50, "dangerous", 1.7),
    (math.inf, "critical", 2.2),
]

# Maps backend tier → UI 3-category enum the frontend already renders.
TIER_TO_UI_CATEGORY = {
    "low": "low",
    "moderate": "low",
    "high": "medium",
    "dangerous": "high",
    "critical": "high",
}


@dataclass
class ViolationRow:
    article_code: str
    weight: int
    occurred_at: date
    at_fault: bool = False


class ComponentEntry(TypedDict):
    article_code: str
    weight: int
    count: int
    recurrence: float
    decay: float
    contribution: float


@dataclass(frozen=True)
class ScoreResult:
    risk_score: float
    safety_score: int
    risk_tier: str
    risk_category_ui: str
    premium_coefficient: float
    accident_factor: float
    discount: float
    behavioral_multiplier: float
    final_premium_kzt: int
    # breakdown is intentionally empty here; the router/seed populates it from
    # KoapArticle.factor_group after the pure engine returns.
    breakdown: dict[str, float] = field(default_factory=dict)
    components: list[ComponentEntry] = field(default_factory=list)


def recurrence_multiplier(count: int) -> float:
    if count <= 1:
        return 1.0
    if count == 2:
        return 1.3
    if count == 3:
        return 1.6
    return 2.0


def time_decay(occurred: date, today: date) -> float:
    # 365-day years match the formула.docx §5 example (decay≈0.9 at 0.527 years).
    years = (today - occurred).days / 365
    if years < 0:
        years = 0
    return math.exp(-K_DECAY * years)


def accident_factor(count: int) -> float:
    # count <= 0 treated as no accidents (clamps negative input to 1.0).
    if count <= 0:
        return 1.0
    if count == 1:
        return 1.2
    if count == 2:
        return 1.5
    return 2.0


def _tier_entry(score: float) -> tuple[str, float]:
    """Return (tier_name, premium_coefficient) for score. No gaps — every
    score lands in exactly one tier."""
    if score < 0:
        score = 0
    for upper, tier, coef in TIERS:
        if score <= upper:
            return tier, coef
    return "critical", 2.2  # unreachable: math.inf catches all


def risk_tier_for(score: float) -> str:
    return _tier_entry(score)[0]


def premium_coefficient_for(score: float) -> float:
    return _tier_entry(score)[1]


def safety_score_from_risk(risk_score: float) -> int:
    """Inverse mapping for UI: 100 · e^(-risk/30), clamped 0..100."""
    raw = 100.0 * math.exp(-risk_score / 30.0)
    return max(0, min(100, round(raw)))


def compute_discount(violations: list[ViolationRow], today: date) -> float:
    """Single best safe-driving discount; not stacked.

    Rules (spec §7 / формула.docx §9):
      5 years with no violations of any kind        → 0.25
      3 years with no at-fault violations AND
        at least one non-at-fault violation within
        the last 2 years (active-but-safe driver)   → 0.15
      1 year with no violations of any kind         → 0.05
      otherwise                                     → 0.0

    Note: a violation within the last year (years_since_any < 1) that is also
    non-at-fault does NOT qualify for the 3-year rule because the driver is not
    "safe" enough — they fall through to 0.0 as intended.
    """
    if not violations:
        return 0.25  # vacuously clean

    last_any = max(v.occurred_at for v in violations)
    at_fault_dates = [v.occurred_at for v in violations if v.at_fault]
    last_at_fault = max(at_fault_dates) if at_fault_dates else None

    years_since_any = (today - last_any).days / 365
    # math.inf sentinel: no at-fault violation ever recorded.
    years_since_at_fault = (today - last_at_fault).days / 365 if last_at_fault else math.inf

    if years_since_any >= 5:
        return 0.25
    # 3-year no-at-fault rule: active driver (violation within last 2 years inclusive)
    # but no at-fault violations for 3+ years.
    if years_since_at_fault >= 3 and years_since_any <= 2:
        return 0.15
    if years_since_any >= 1:
        return 0.05
    return 0.0


def compute_score(
    violations: list[ViolationRow],
    accident_count: int,
    today: date,
    base_premium: int = BASE_PREMIUM_KZT,
) -> ScoreResult:
    # Group by article_code → list of rows (all share the same weight per article).
    grouped: dict[str, list[ViolationRow]] = defaultdict(list)
    for v in violations:
        grouped[v.article_code].append(v)

    risk_score = 0.0
    components: list[ComponentEntry] = []

    for code, rows in grouped.items():
        weight = rows[0].weight
        count = len(rows)
        recur = recurrence_multiplier(count)
        latest = max(r.occurred_at for r in rows)
        decay = time_decay(latest, today)
        contribution = weight * count * recur * decay
        risk_score += contribution
        components.append(
            ComponentEntry(
                article_code=code,
                weight=weight,
                count=count,
                recurrence=recur,
                decay=round(decay, 4),
                contribution=round(contribution, 2),
            )
        )

    risk_score = round(risk_score, 2)
    af = accident_factor(accident_count)
    discount = compute_discount(violations, today)
    behavioral = round(1 + ALPHA * risk_score, 4)
    final_premium = round(base_premium * behavioral * af * (1 - discount))

    tier, coef = _tier_entry(risk_score)

    return ScoreResult(
        risk_score=risk_score,
        safety_score=safety_score_from_risk(risk_score),
        risk_tier=tier,
        risk_category_ui=TIER_TO_UI_CATEGORY[tier],
        premium_coefficient=coef,
        accident_factor=af,
        discount=discount,
        behavioral_multiplier=behavioral,
        final_premium_kzt=final_premium,
        components=components,
    )
