from datetime import date

import pytest

from app.scoring import (
    ViolationRow,
    compute_score,
    recurrence_multiplier,
    risk_tier_for,
    safety_score_from_risk,
)

# --- The two docx examples are the locked contract for the engine ---


def test_driver_a_positive_low_risk_174556_kzt():
    """
    Driver A from формула.docx §8 — Positive (Low Risk).
    Single minor speeding (W=2) 2 years ago, 3 clean years (no accidents).
    Expected: risk_score=1.34, AF=1.0, D=0.15, final_premium=174 556 ₸.
    """
    today = date(2026, 5, 21)
    violations = [
        ViolationRow(
            article_code="Art.592",
            weight=2,
            occurred_at=date(2024, 5, 21),  # exactly 2 years ago
            at_fault=False,
        ),
    ]
    result = compute_score(
        violations=violations,
        accident_count=0,
        today=today,
    )
    assert result.risk_score == pytest.approx(1.34, abs=0.01)
    assert result.accident_factor == 1.0
    assert result.discount == 0.15
    assert result.final_premium_kzt == 174_556
    assert result.risk_tier == "low"
    assert result.premium_coefficient == 0.9


def test_driver_b_negative_critical_risk_653520_kzt():
    """
    Driver B from формула.docx §8 — Negative (Critical Risk).
    DUI (W=25, today), Red Light (W=8, today), Speeding ×3 (W=6) with
    most recent ~0.527 years ago giving decay≈0.9.
    Expected: risk_score=58.92, AF=1.5, D=0, final_premium=653 520 ₸.
    """
    today = date(2026, 5, 21)
    # ln(0.9)/(-0.2) = 0.5268 years → 192.42 days
    most_recent_speeding = date(2025, 11, 10)  # ≈ 192 days before today
    violations = [
        ViolationRow(
            article_code="Art.608 Part 1",
            weight=25,
            occurred_at=today,
            at_fault=True,
        ),
        ViolationRow(
            article_code="Art.599",
            weight=8,
            occurred_at=today,
            at_fault=False,
        ),
        ViolationRow(
            article_code="Art.592 Part 3-1",
            weight=6,
            occurred_at=date(2025, 1, 1),
            at_fault=False,
        ),
        ViolationRow(
            article_code="Art.592 Part 3-1",
            weight=6,
            occurred_at=date(2025, 6, 1),
            at_fault=False,
        ),
        ViolationRow(
            article_code="Art.592 Part 3-1",
            weight=6,
            occurred_at=most_recent_speeding,
            at_fault=False,
        ),
    ]
    result = compute_score(
        violations=violations,
        accident_count=2,
        today=today,
    )
    assert result.risk_score == pytest.approx(58.92, abs=0.05)
    assert result.accident_factor == 1.5
    assert result.discount == 0.0
    # 200000 × 2.1784 × 1.5 × 1 = 653,520
    assert result.final_premium_kzt == pytest.approx(653_520, abs=10)
    assert result.risk_tier == "critical"
    assert result.premium_coefficient == 2.2


# --- Boundary tests for the 5 tiers ---


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, "low"),
        (5, "low"),
        (5.001, "moderate"),  # fractional just above the boundary
        (5.5, "moderate"),    # regression: previously fell through to "critical"
        (6, "moderate"),
        (15, "moderate"),
        (15.5, "high"),       # regression
        (16, "high"),
        (30, "high"),
        (30.5, "dangerous"),  # regression
        (31, "dangerous"),
        (50, "dangerous"),
        (50.5, "critical"),
        (51, "critical"),
        (1000, "critical"),
    ],
)
def test_risk_tier_boundaries(score, expected):
    assert risk_tier_for(score) == expected


# --- recurrence_multiplier table ---


@pytest.mark.parametrize(
    "idx,mult",
    [(1, 1.0), (2, 1.3), (3, 1.6), (4, 2.0), (10, 2.0)],
)
def test_recurrence_multiplier(idx, mult):
    assert recurrence_multiplier(idx) == mult


# --- safety_score inverse from §6 ---


def test_safety_score_zero_risk_is_100():
    assert safety_score_from_risk(0) == 100


def test_safety_score_high_risk_low():
    # risk_score = 60 → round(100 * exp(-2)) = round(13.53) = 14
    assert safety_score_from_risk(60) == 14


# --- Discount derivation ---


def test_discount_5_years_clean():
    today = date(2026, 5, 21)
    # No violations at all
    result = compute_score([], accident_count=0, today=today)
    assert result.discount == 0.25


def test_discount_1_year_no_violations():
    today = date(2026, 5, 21)
    violations = [
        ViolationRow(
            article_code="Art.592",
            weight=2,
            occurred_at=date(2024, 1, 1),  # > 1 year, < 3 years
            at_fault=False,
        ),
    ]
    result = compute_score(violations, accident_count=0, today=today)
    assert result.discount == 0.05


def test_discount_3_years_no_at_fault():
    today = date(2026, 5, 21)
    violations = [
        ViolationRow(
            article_code="Art.591",
            weight=5,
            occurred_at=date(2025, 1, 1),  # < 1 year — recent non-at-fault
            at_fault=False,
        ),
    ]
    result = compute_score(violations, accident_count=0, today=today)
    # Recent violation kills 1y and 5y; never at-fault → 3y rule applies
    assert result.discount == 0.15
