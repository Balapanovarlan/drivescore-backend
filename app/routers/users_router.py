from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.auth import hash_password, require_admin
from app.database import get_db
from app.models import User
from app.schemas import CreateUserIn, UserOut

router = APIRouter(prefix="/api/users", tags=["users"])

ALLOWED_ROLES = {"admin", "manager"}


@router.get("", response_model=list[UserOut])
async def list_users(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserOut]:
    users = await crud.list_users(db)
    return [UserOut.model_validate(u) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserIn,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    if payload.role not in ALLOWED_ROLES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"role must be one of {sorted(ALLOWED_ROLES)}",
        )
    existing = await crud.get_user_by_email(db, payload.email)
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = await crud.create_user(
        db,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    return UserOut.model_validate(user)
