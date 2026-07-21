"""Reusable model mixins.

Every entity model composes these instead of redeclaring the same columns.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Adds `created_at` / `updated_at`, managed by the database itself."""

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    """Marks a record inactive instead of physically deleting it.

    Farm/health/financial records need an audit trail — hard deletes would
    silently break historical reports and AI trend analysis.
    """

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
