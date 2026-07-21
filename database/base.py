"""SQLAlchemy declarative base shared by every model in the project."""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Root declarative base. All ORM models inherit from this."""
