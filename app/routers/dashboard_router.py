from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import DashboardSummary, HistogramBucket

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def summary(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    agg = await crud.dashboard_aggregates(db)
    total: int = agg["total"]
    snaps = agg["latest_snaps"]

    risk_dist = {"low": 0, "medium": 0, "high": 0}
    score_sum = 0
    histogram_counts = [0] * 10  # 0-9, 10-19, ..., 90-100
    high_risk = 0
    weighted_premium = 0.0

    for s in snaps:
        # risk_tier is the 3-cat UI category itself (low/medium/high).
        # Legacy 5-tier values fall back to "medium" so a stale snapshot
        # doesn't blow up the dashboard before the next recompute.
        ui_cat = s.risk_tier if s.risk_tier in risk_dist else "medium"
        risk_dist[ui_cat] += 1
        score_sum += s.safety_score
        idx = min(9, s.safety_score // 10)
        histogram_counts[idx] += 1
        if ui_cat == "high":
            high_risk += 1
        weighted_premium += float(s.premium_coef)

    n = len(snaps) if snaps else 1
    avg = round(score_sum / n) if snaps else 0
    high_share = round(100 * high_risk / n) if snaps else 0
    loss_ratio = round(weighted_premium / n, 2) if snaps else 0.0

    histogram = []
    for i, count in enumerate(histogram_counts):
        if i <= 2:
            band = "high"
        elif i <= 5:
            band = "medium"
        else:
            band = "low"
        lo = i * 10
        hi = lo + 9 if i < 9 else 100
        histogram.append(HistogramBucket(range=f"{lo}-{hi}", count=count, band=band))

    return DashboardSummary(
        total_drivers=total,
        average_score=avg,
        high_risk_share=high_share,
        estimated_loss_ratio=loss_ratio,
        risk_distribution=risk_dist,
        score_histogram=histogram,
    )
