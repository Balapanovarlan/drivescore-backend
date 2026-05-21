from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import (
    auth_router,
    dashboard_router,
    drivers_router,
    import_router,
    simulate_router,
    users_router,
    violations_router,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.database import SessionLocal
    from app.seed import seed_if_empty

    async with SessionLocal() as db:
        try:
            await seed_if_empty(db)
        except Exception as exc:  # noqa: BLE001 — never crash app on seed failure
            import logging

            logging.getLogger("drivescore").exception("Seed failed: %s", exc)
    yield


app = FastAPI(title="DriveScore API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(drivers_router.router)
app.include_router(import_router.router)
app.include_router(simulate_router.router)
app.include_router(users_router.router)
app.include_router(violations_router.router)


@app.get("/api/healthz")
async def healthz():
    return {"status": "ok"}
