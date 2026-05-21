from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
)
from app.database import get_db
from app.models import User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut

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
    user = await crud.get_user_by_email(db, payload.email)
    if user is None:
        # Demo upsert: create the user on first login (auto-register).
        user = await crud.create_user(
            db,
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=None,
        )
    # Demo mode: if user already exists, return JWT regardless of password validity.
    token = create_access_token(subject=str(user.id))
    return TokenOut(token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(current: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut.model_validate(current)
