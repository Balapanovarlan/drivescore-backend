from datetime import date

import pytest

from app.scoring import (
    K_SCALE,
    ViolationRow,
    compute_score,
    recurrence_multiplier,
    safety_score_from_risk,
    ui_category_from_safety,
)

# --- The two doc examples (другаяформула.docx) are the locked contract ---


def test_good_scenario_safe_driver():
    """
    Good Scenario from другаяформула.docx.
    1 seatbelt violation (W=3), F=1, R=1.0, decay ≈ 0.5 (occurred ~1.386y ago).
    No accidents.
    Expected raw_score = 1.5; with k=0.07: premium = 22000 · (1 + 0.07·1.5) = 24 310 ₸.
    """
    today = date(2026, 5, 27)
    # 506 days back from today → t = 506/365 ≈ 1.386y → D = e^(-0.5·1.386) = 0.5
    occurred = date(2025, 1, 6)
    violations = [
        ViolationRow(
            article_code="Art.593",
            weight=3,
            occurred_at=occurred,
            at_fault=False,
        ),
    ]
    result = compute_score(violations, accident_count=0, today=today)

    assert result.risk_score == pytest.approx(1.5, abs=0.01)
    assert result.accident_factor == 1.0  # vestigial
    assert result.discount == 0.0          # vestigial
    assert result.premium_coefficient == pytest.approx(1.105, abs=0.005)
    assert result.final_premium_kzt == pytest.approx(24_310, abs=10)
    assert result.risk_category_ui == "low"
    assert result.risk_tier == "low"


def test_risky_scenario_high_risk_driver():
    """
    Risky Scenario from другаяформула.docx.
    Inputs: 2 speeding (W=12, today → D=1), 1 red light (W=10, today → D=1), 1 accident.
    Expected raw_score = 26.4 + 10 + 10 = 46.4.
    With k=0.07: premium = round(22000 · (1 + 0.07·46.4)) = round(22000·4.248) = 93 456 ₸.

    Note: this differs from the doc's printed 44 352 ₸ because the doc's examples
    use k=0.02 inline, while we follow the calibration block (k=0.07).
    """
    today = date(2026, 5, 27)
    violations = [
        ViolationRow(article_code="Art.592 Part 3-1", weight=12, occurred_at=today),
        ViolationRow(article_code="Art.592 Part 3-1", weight=12, occurred_at=today),
        ViolationRow(article_code="Art.599", weight=10, occurred_at=today),
    ]
    result = compute_score(violations, accident_count=1, today=today)

    assert result.risk_score == pytest.approx(46.4, abs=0.05)
    assert result.accident_factor == 1.0
    assert result.discount == 0.0
    assert result.premium_coefficient == pytest.approx(1 + K_SCALE * 46.4, abs=0.005)
    assert result.final_premium_kzt == pytest.approx(93_456, abs=10)
    assert result.risk_category_ui == "high"
    assert result.risk_tier == "high"


# --- recurrence_multiplier: linear R = 1 + 0.1·(n − 1) ---


@pytest.mark.parametrize(
    "n,expected",
    [(0, 1.0), (1, 1.0), (2, 1.1), (3, 1.2), (4, 1.3), (5, 1.4), (10, 1.9)],
)
def test_recurrence_multiplier_linear(n, expected):
    assert recurrence_multiplier(n) == pytest.approx(expected, abs=1e-6)


# --- safety_score: inverse exponential mapping (unchanged) ---


def test_safety_score_zero_risk_is_100():
    assert safety_score_from_risk(0) == 100


def test_safety_score_high_risk_low():
    # risk_score = 60 → round(100 · exp(-2)) = 14
    assert safety_score_from_risk(60) == 14


# --- UI category from safety_score (3-cat, replaces 5-tier) ---


@pytest.mark.parametrize(
    "safety,expected",
    [
        (100, "low"),
        (70, "low"),
        (69, "medium"),
        (50, "medium"),
        (30, "medium"),
        (29, "high"),
        (0, "high"),
    ],
)
def test_ui_category_boundaries(safety, expected):
    assert ui_category_from_safety(safety) == expected


# --- Empty input degenerate case ---


def test_no_violations_no_accidents_zero_score():
    today = date(2026, 5, 27)
    result = compute_score([], accident_count=0, today=today)
    assert result.risk_score == 0.0
    assert result.safety_score == 100
    assert result.premium_coefficient == 1.0
    assert result.final_premium_kzt == 22_000
    assert result.risk_category_ui == "low"


# --- Accident penalty contributes additively, before k-scaling ---


def test_accident_only_adds_10_per_accident():
    """No violations, 2 accidents → raw_score = 20."""
    today = date(2026, 5, 27)
    result = compute_score([], accident_count=2, today=today)
    assert result.risk_score == 20.0
    # premium = 22000 · (1 + 0.07·20) = 22000 · 2.4 = 52800
    assert result.final_premium_kzt == 52_800
