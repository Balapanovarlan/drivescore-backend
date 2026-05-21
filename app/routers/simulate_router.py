from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.crud import aggregate_breakdown
from app.database import get_db
from app.koap_catalogue import KOAP_BY_CODE
from app.models import User
from app.schemas import ScoreResultOut, SimulateIn
from app.scoring import ViolationRow, compute_score

router = APIRouter(prefix="/api/score", tags=["scoring"])


@router.post("/simulate", response_model=ScoreResultOut)
async def simulate(
    payload: SimulateIn,
    _: Annotated[User, Depends(get_current_user)],
    __: Annotated[AsyncSession, Depends(get_db)],
):
    rows: list[ViolationRow] = []
    for v in payload.violations:
        article = KOAP_BY_CODE.get(v.article_code)
        if article is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Unknown article: {v.article_code}",
            )
        rows.append(
            ViolationRow(
                article_code=v.article_code,
                weight=article["weight"],
                occurred_at=v.occurred_at,
                at_fault=v.at_fault,
            )
        )
    if payload.base_premium:
        result = compute_score(
            rows, payload.accident_count, today=date.today(), base_premium=payload.base_premium
        )
    else:
        result = compute_score(rows, payload.accident_count, today=date.today())
    breakdown = aggregate_breakdown(result.components)
    return ScoreResultOut(
        score=result.safety_score,
        risk_category=result.risk_category_ui,
        risk_tier=result.risk_tier,
        premium_coefficient=result.premium_coefficient,
        final_premium_kzt=result.final_premium_kzt,
        accident_factor=result.accident_factor,
        discount=result.discount,
        breakdown=breakdown,
    )
