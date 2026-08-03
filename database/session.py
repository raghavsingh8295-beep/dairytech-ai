"""Database engine and session management.

All database access in the application goes through `get_db_session()`,
a context manager that commits on success, rolls back on error, and always
closes the session. Controllers/services must never hold a session open
across UI event-loop turns.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings
from utils.exceptions import AppError
from utils.logger import get_logger

logger = get_logger(__name__)

_connect_args = {}
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
if _is_sqlite:
    # Allow the connection to be used from a background thread (e.g. an
    # AI/report job running off the Tkinter main thread) while a single
    # session instance still stays confined to one thread at a time.
    _connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    connect_args=_connect_args,
    future=True,
    # Serverless Postgres hosts (e.g. Neon) suspend their compute after a
    # period of inactivity and drop any connection that was pooled before
    # the suspend — pool_pre_ping validates a connection with a cheap
    # round-trip before handing it to a request, transparently reconnecting
    # instead of surfacing psycopg's AdminShutdown as a 500. A no-op for
    # SQLite, which never drops connections underneath us this way.
    pool_pre_ping=True,
)

if _is_sqlite:

    @event.listens_for(Engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        """SQLite ignores FOREIGN KEY constraints unless explicitly enabled per-connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Yield a transactional session; commits on success, rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except AppError as exc:
        session.rollback()
        logger.warning("Database session rolled back: %s", exc)
        raise
    except Exception:
        session.rollback()
        logger.exception("Database session rolled back due to an unexpected error.")
        raise
    finally:
        session.close()
