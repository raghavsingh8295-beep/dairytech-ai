"""Database initialization helpers.

`init_database()` creates all tables registered on `Base.metadata` at the
time it is called — which is why every model module must be imported
before this runs (see the `import models` note inside the function).
"""
from __future__ import annotations

from sqlalchemy import text

from config.settings import settings
from database.base import Base
from database.session import engine
from utils.logger import get_logger

logger = get_logger(__name__)


def init_database() -> None:
    """Create all tables that don't already exist."""
    import models  # noqa: F401  (ensures every model is registered on Base.metadata)

    if not settings.DATABASE_URL.startswith("sqlite"):
        # `vector` backs the AI Dairy Assistant's book_chunks.embedding
        # column; `pg_trgm` backs its keyword-search leg. Both are
        # idempotent and Neon whitelists them without needing superuser.
        # SQLite has neither concept, so this only runs on Postgres.
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized at %s", engine.url)


def check_connection() -> bool:
    """Verify the database is reachable. Returns True on success."""
    try:
        with engine.connect():
            return True
    except Exception:
        logger.exception("Database connection check failed.")
        return False
