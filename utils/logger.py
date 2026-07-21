"""Application-wide logging configuration.

Every module gets its logger via `get_logger(__name__)` so log lines are
traceable to their source. Configuration happens exactly once per process.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from config.settings import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root_logger() -> None:
    global _configured
    if _configured:
        return

    root = logging.getLogger("dairytech")
    root.setLevel(settings.LOG_LEVEL)
    root.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = RotatingFileHandler(
        settings.LOGS_DIR / "dairytech.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the `dairytech` hierarchy."""
    _configure_root_logger()
    return logging.getLogger(f"dairytech.{name}")
