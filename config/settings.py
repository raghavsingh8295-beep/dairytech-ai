"""
Centralized application configuration.

All paths, environment-dependent values, and app-wide constants live here.
Nothing outside this module should read `os.environ` directly — that keeps
every configurable value discoverable in one place and makes the eventual
SQLite -> PostgreSQL migration a one-line change (DATABASE_URL below).
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR: Path = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_or_create_jwt_secret() -> str:
    """Real deployments must set JWT_SECRET_KEY via env. This fallback only
    exists so local API/mobile testing works with zero setup — it persists
    to a gitignored file so restarting the server doesn't invalidate every
    token a tester is holding."""
    env_value = os.getenv("JWT_SECRET_KEY")
    if env_value:
        return env_value
    secret_file = BASE_DIR / ".jwt_secret"
    if secret_file.exists():
        return secret_file.read_text().strip()
    secret = secrets.token_hex(32)
    secret_file.write_text(secret)
    return secret


@dataclass(frozen=True)
class Settings:
    """Immutable, process-wide application settings."""

    APP_NAME: str = "DairyTech AI"
    APP_VERSION: str = "0.1.0"

    BASE_DIR: Path = BASE_DIR
    ASSETS_DIR: Path = BASE_DIR / "assets"
    LOGS_DIR: Path = BASE_DIR / "logs"
    EXPORTS_DIR: Path = BASE_DIR / "exports"

    # Database — swapping to PostgreSQL later only requires overriding
    # DATABASE_URL in .env, e.g. postgresql+psycopg://user:pass@host/dbname
    DATABASE_URL: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            f"sqlite:///{(BASE_DIR / 'database' / 'dairytech.db').as_posix()}",
        )
    )
    DATABASE_ECHO: bool = field(default_factory=lambda: _get_bool("DATABASE_ECHO", False))

    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # UI
    APPEARANCE_MODE: str = field(default_factory=lambda: os.getenv("APPEARANCE_MODE", "System"))
    COLOR_THEME: str = field(default_factory=lambda: os.getenv("COLOR_THEME", "blue"))
    WINDOW_MIN_WIDTH: int = 1100
    WINDOW_MIN_HEIGHT: int = 680

    # Mobile API (JWT auth) — JWT_SECRET_KEY must be set explicitly via env
    # in any real deployment; the auto-generated dev fallback (see
    # _load_or_create_dev_secret below) only exists so local testing doesn't
    # require manual setup, and persists to a gitignored file so tokens
    # survive a server restart during development.
    JWT_SECRET_KEY: str = field(default_factory=_load_or_create_jwt_secret)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_DAYS: int = field(default_factory=lambda: int(os.getenv("JWT_EXPIRY_DAYS", "30")))

    def ensure_directories(self) -> None:
        """Create runtime directories that are not tracked in git."""
        for directory in (self.LOGS_DIR, self.EXPORTS_DIR, self.BASE_DIR / "database"):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
