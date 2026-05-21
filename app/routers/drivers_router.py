from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.auth import get_current_user
from app.database import get_db
from app.koap_catalogue import KOAP_BY_CODE
from app.models import User
from app.schemas import DriverDetail, DriverListItem, ScoreHistoryPoint, ViolationOut

router = APIRouter(prefix="/api/drivers", tags=["drivers"])


def _severity(weight: int) -> str:
    if weight >= 25:
        return "Critical"
    if weight >= 15:
        return "High"
    if weight >= 8:
        return "Medium"
    return "Low"


def _violation_out(v) -> ViolationOut:
    article = KOAP_BY_CODE.get(v.article_code, {})
    return ViolationOut(
        id=v.id,
        article_code=v.article_code,
        article_name=article.get("name", v.article_code),
        occurred_at=v.occurred_at,
        fine_kzt=v.fine_kzt,
        at_fault=v.at_fault,
        severity=_severity(article.get("weight", 0)),
        factor_group=article.get("factor_group", "accident"),
    )


@router.get("", response_model=list[DriverListItem])
async def list_drivers(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    drivers = await crud.list_drivers(db)
    today = date.today()
    out: list[DriverListItem] = []
    for d in drivers:
        violations, result, breakdown = await crud.compute_driver_score(db, d.id, today)
        out.append(
            DriverListItem(
                id=d.id,
                full_name=d.full_name,
                license_number=d.license_number,
                experience_years=d.experience_years,
                score=result.safety_score,
                risk_category=result.risk_category_ui,
                risk_tier=result.risk_tier,
                premium_coefficient=result.premium_coefficient,
                breakdown=breakdown,
            )
        )
    return out


@router.get("/{driver_id}", response_model=DriverDetail)
async def get_driver(
    driver_id: str,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    driver = await crud.get_driver(db, driver_id)
    if driver is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Driver not found")
    today = date.today()
    violations, result, breakdown = await crud.compute_driver_score(db, driver_id, today)
    snaps = await crud.get_driver_snapshots(db, driver_id)
    score_history = [ScoreHistoryPoint(period=s.period, score=s.safety_score) for s in snaps]

    # Build legacy scoreInput / events for the existing frontend shape.
    score_input = {
        "mileageKm": driver.mileage_km,
        "speeding": sum(
            1
            for v in violations
            if KOAP_BY_CODE.get(v.article_code, {}).get("factor_group") == "speeding"
        ),
        "harshBraking": sum(
            1
            for v in violations
            if KOAP_BY_CODE.get(v.article_code, {}).get("factor_group") == "harshBraking"
        ),
        "harshAcceleration": sum(
            1
            for v in violations
            if KOAP_BY_CODE.get(v.article_code, {}).get("factor_group") == "harshAcceleration"
        ),
        "phoneUsage": sum(
            1
            for v in violations
            if KOAP_BY_CODE.get(v.article_code, {}).get("factor_group") == "phoneUsage"
        ),
        "redLight": sum(
            1
            for v in violations
            if KOAP_BY_CODE.get(v.article_code, {}).get("factor_group") == "redLight"
        ),
        "accident": sum(
            1
            for v in violations
            if KOAP_BY_CODE.get(v.article_code, {}).get("factor_group") == "accident"
        ),
    }
    events = [
        {
            "id": str(v.id),
            "type": KOAP_BY_CODE.get(v.article_code, {}).get("factor_group", "accident"),
            "occurredAt": v.occurred_at.isoformat(),
            "severity": _severity(KOAP_BY_CODE.get(v.article_code, {}).get("weight", 0)),
        }
        for v in violations[:20]
    ]
    violations_out = [_violation_out(v) for v in violations]

    return DriverDetail(
        id=driver.id,
        full_name=driver.full_name,
        license_number=driver.license_number,
        experience_years=driver.experience_years,
        city=driver.city,
        added_at=driver.added_at,
        score_input=score_input,
        events=events,
        violations=violations_out,
        score_history=score_history,
        score=result.safety_score,
        risk_category=result.risk_category_ui,
        risk_tier=result.risk_tier,
        premium_coefficient=result.premium_coefficient,
        final_premium_kzt=result.final_premium_kzt,
        accident_factor=result.accident_factor,
        discount=result.discount,
        breakdown=breakdown,
    )
