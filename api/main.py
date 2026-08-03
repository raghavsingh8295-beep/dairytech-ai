"""FastAPI application entry point for the trimTAB mobile/API backend.

Run with:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

`--host 0.0.0.0` (not the default 127.0.0.1) is required so phones on the
same WiFi network can reach it, not just processes on this machine.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routers import auth, cows, daily_records, farms, health, insights, milk_quality, users
from config.settings import settings
from database.init_db import init_database
from utils.exceptions import AppError


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield


app = FastAPI(title=f"{settings.APP_NAME} API", version=settings.APP_VERSION, lifespan=lifespan)

# Permissive for local development — a mobile app's own HTTP client doesn't
# enforce CORS the way a browser does, but this also covers a future web
# frontend hitting the same API from a different origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """Every controller-layer failure (permission denied, not found,
    validation) becomes a 400 with the same message the desktop UI shows —
    one error-handling seam already proven across all 10 desktop modules,
    not reimplemented per endpoint."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.include_router(auth.router)
app.include_router(farms.router)
app.include_router(cows.router)
app.include_router(daily_records.router)
app.include_router(health.router)
app.include_router(users.router)
app.include_router(milk_quality.router)
app.include_router(insights.router)

settings.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
# Serves farm/cow photos (assets/images/farms/*, assets/images/cows/*) so the
# mobile app can load them by URL — the desktop app reads these off local
# disk directly and has never needed an HTTP path before.
app.mount("/media", StaticFiles(directory=str(settings.ASSETS_DIR)), name="media")


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "app": settings.APP_NAME}
