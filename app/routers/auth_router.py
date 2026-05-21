from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import User
from app.schemas import ChangePasswordIn, LoginIn, RegisterIn, TokenOut, UserOut
from app.security import login_throttler

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, db: Annotated[AsyncSession, Depends(get_db)]) -> TokenOut:
    existing = await crud.get_user_by_email(db, payload.email)
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = await crud.create_user(
        db,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    token = create_access_token(subject=str(user.id))
    return TokenOut(token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, db: Annotated[AsyncSession, Depends(get_db)]) -> TokenOut:
    allowed, retry_after = login_throttler.check(payload.email)
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many failed attempts. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )

    user = await crud.get_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        locked, info = login_throttler.record_failure(payload.email)
        if locked:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Too many failed attempts. Account locked for {info}s.",
                headers={"Retry-After": str(info)},
            )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")

    login_throttler.record_success(payload.email)
    token = create_access_token(subject=str(user.id))
    return TokenOut(token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(current: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut.model_validate(current)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordIn,
    current: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if not verify_password(payload.current_password, current.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Current password is incorrect."
        )
    current.password_hash = hash_password(payload.new_password)
    await db.commit()
