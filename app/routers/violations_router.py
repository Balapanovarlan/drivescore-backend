from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db
from app.schemas import KoapArticleOut

router = APIRouter(prefix="/api", tags=["catalogue"])


@router.get("/koap-articles", response_model=list[KoapArticleOut])
async def list_articles(db: Annotated[AsyncSession, Depends(get_db)]):
    return await crud.list_koap_articles(db)
