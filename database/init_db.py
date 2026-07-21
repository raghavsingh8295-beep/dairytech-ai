"""Database initialization helpers.

`init_database()` creates all tables registered on `Base.metadata` at the
time it is called — which is why every model module must be imported
before this runs (see the `import models` note inside the function).
"""
from __future__ import annotations

from database.base import Base
from database.session import engine
from utils.logger import get_logger

logger = get_logger(__name__)


def init_database() -> None:
    """Create all tables that don't already exist."""
    import models  # noqa: F401  (ensures every model is registered on Base.metadata)

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
