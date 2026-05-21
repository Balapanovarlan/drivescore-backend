import csv
import io
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.auth import get_current_user
from app.database import get_db
from app.koap_catalogue import KOAP_BY_CODE
from app.models import Driver, User, Violation
from app.schemas import ImportError as ImportErrorSchema
from app.schemas import ImportResultOut

router = APIRouter(prefix="/api/import", tags=["import"])


def _to_bool(s: str) -> bool:
    return s.strip().lower() in {"true", "1", "yes", "y", "да"}


def _detect_delimiter(content: str) -> str:
    """Return ',' or ';' based on the header line. Excel-RU/KZ exports often
    use ';' because comma is the decimal separator in those locales."""
    first_line = content.splitlines()[0] if content else ""
    return ";" if first_line.count(";") > first_line.count(",") else ","


REQUIRED_HEADERS = {"license_number", "koap_article", "occurred_at"}


@router.post("/violations", response_model=ImportResultOut)
async def import_violations(
    file: Annotated[UploadFile, File(...)],
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    content = (await file.read()).decode("utf-8-sig", errors="replace")
    delimiter = _detect_delimiter(content)
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    if not reader.fieldnames or not REQUIRED_HEADERS.issubset(set(reader.fieldnames)):
        from fastapi import HTTPException, status

        missing = REQUIRED_HEADERS - set(reader.fieldnames or [])
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"CSV is missing required headers: {sorted(missing)}. "
            f"Required: license_number, koap_article, occurred_at; optional: fine_kzt, at_fault.",
        )

    errors: list[ImportErrorSchema] = []
    imported = 0
    touched_driver_ids: set[str] = set()

    # Pre-load drivers by license number
    drivers_res = await db.execute(select(Driver))
    drivers = {d.license_number: d for d in drivers_res.scalars().all()}

    for i, row in enumerate(reader, start=1):
        license_no = (row.get("license_number") or "").strip()
        article_code = (row.get("koap_article") or "").strip()
        occurred_raw = (row.get("occurred_at") or "").strip()
        fine_raw = (row.get("fine_kzt") or "").strip()
        at_fault_raw = (row.get("at_fault") or "false").strip()

        driver = drivers.get(license_no)
        if driver is None:
            errors.append(ImportErrorSchema(row=i, message=f"Unknown license: {license_no}"))
            continue
        if article_code not in KOAP_BY_CODE:
            errors.append(ImportErrorSchema(row=i, message=f"Unknown article: {article_code}"))
            continue
        try:
            occurred_at = date.fromisoformat(occurred_raw)
        except ValueError:
            errors.append(ImportErrorSchema(row=i, message=f"Bad date: {occurred_raw}"))
            continue

        # Compute recurrence_idx = 1 + existing count of this article for this driver
        existing = await db.execute(
            select(Violation).where(
                Violation.driver_id == driver.id,
                Violation.article_code == article_code,
            )
        )
        existing_count = len(list(existing.scalars().all()))
        violation = Violation(
            driver_id=driver.id,
            article_code=article_code,
            occurred_at=occurred_at,
            fine_kzt=int(fine_raw) if fine_raw else None,
            at_fault=_to_bool(at_fault_raw),
            recurrence_idx=existing_count + 1,
        )
        db.add(violation)
        imported += 1
        touched_driver_ids.add(driver.id)

    await db.commit()

    # Recompute current-month snapshot for each touched driver
    today = date.today()
    period = today.strftime("%Y-%m")
    for driver_id in touched_driver_ids:
        violations, result, _bd = await crud.compute_driver_score(db, driver_id, today)
        await crud.upsert_snapshot(
            db,
            driver_id=driver_id,
            period=period,
            risk_score=result.risk_score,
            safety_score=result.safety_score,
            risk_tier=result.risk_tier,
            premium_coef=result.premium_coefficient,
        )

    return ImportResultOut(
        imported_records=imported,
        recomputed_drivers=len(touched_driver_ids),
        errors=errors,
    )
