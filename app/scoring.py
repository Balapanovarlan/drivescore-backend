"""
Pure scoring engine — mirrors другаяформула.docx (composite UBI/PHYD model).

Formula:
    RiskScore = k · [ Σ(W_i · F_i · R_i · D_i)  +  10 · n_accidents ]
    Premium   = BasePremium · (1 + RiskScore)

where
    k  = 0.07              (calibration block of the spec)
    R(n) = 1 + 0.1·(n − 1) (linear recurrence)
    D(t) = e^(−0.5 · t)    (exponential decay, λ=0.5; t in years)
    BasePremium = 22 000 ₸
    AccidentPenalty per accident = 10  (additive into raw score, before k)

No database imports. Inputs are plain dataclasses; outputs are plain dataclasses.
Used by /drivers/{id}, /score/simulate, seed, and snapshot recomputation.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import TypedDict

# Spec-locked defaults. Settings can override BASE_PREMIUM_KZT per request
# (e.g. /score/simulate with base_premium override).
K_SCALE = 0.07
K_DECAY = 0.5
BASE_PREMIUM_KZT = 22_000
ACCIDENT_PENALTY = 10


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
    risk_score: float            # raw score: Σ(W·F·R·D) + 10·n_accidents
    safety_score: int            # 0..100, derived from risk_score
    risk_tier: str               # 3-cat: low/medium/high  (synonym of risk_category_ui)
    risk_category_ui: str        # 3-cat: low/medium/high
    premium_coefficient: float   # = 1 + k · risk_score  (behavioral multiplier)
    accident_factor: float       # vestigial: always 1.0 (accidents now in risk_score)
    discount: float              # vestigial: always 0.0 (no safe-driver bonus in new model)
    behavioral_multiplier: float # same as premium_coefficient
    final_premium_kzt: int
    breakdown: dict[str, float] = field(default_factory=dict)
    components: list[ComponentEntry] = field(default_factory=list)


def recurrence_multiplier(count: int) -> float:
    """R(n) = 1 + 0.1·(n − 1); clamps to 1.0 for count <= 1."""
    if count <= 1:
        return 1.0
    return round(1.0 + 0.1 * (count - 1), 4)


def time_decay(occurred: date, today: date) -> float:
    years = (today - occurred).days / 365
    if years < 0:
        years = 0
    return math.exp(-K_DECAY * years)


def safety_score_from_risk(risk_score: float) -> int:
    """Inverse mapping for UI: 100 · e^(-risk/30), clamped 0..100."""
    raw = 100.0 * math.exp(-risk_score / 30.0)
    return max(0, min(100, round(raw)))


def ui_category_from_safety(safety_score: int) -> str:
    """3-category mapping for UI badge. Replaces the old 5-tier system."""
    if safety_score >= 70:
        return "low"
    if safety_score >= 30:
        return "medium"
    return "high"


def compute_score(
    violations: list[ViolationRow],
    accident_count: int,
    today: date,
    base_premium: int = BASE_PREMIUM_KZT,
) -> ScoreResult:
    grouped: dict[str, list[ViolationRow]] = defaultdict(list)
    for v in violations:
        grouped[v.article_code].append(v)

    raw_score = 0.0
    components: list[ComponentEntry] = []

    for code, rows in grouped.items():
        weight = rows[0].weight
        count = len(rows)
        recur = recurrence_multiplier(count)
        latest = max(r.occurred_at for r in rows)
        decay = time_decay(latest, today)
        contribution = weight * count * recur * decay
        raw_score += contribution
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

    # Additive accident penalty — added BEFORE k-scaling.
    accidents = max(0, accident_count)
    raw_score += ACCIDENT_PENALTY * accidents
    raw_score = round(raw_score, 2)

    behavioral = round(1 + K_SCALE * raw_score, 4)
    final_premium = round(base_premium * behavioral)

    safety = safety_score_from_risk(raw_score)
    cat = ui_category_from_safety(safety)

    return ScoreResult(
        risk_score=raw_score,
        safety_score=safety,
        risk_tier=cat,                 # 3-cat now; same as risk_category_ui
        risk_category_ui=cat,
        premium_coefficient=behavioral,
        accident_factor=1.0,           # vestigial
        discount=0.0,                  # vestigial
        behavioral_multiplier=behavioral,
        final_premium_kzt=final_premium,
        components=components,
    )
