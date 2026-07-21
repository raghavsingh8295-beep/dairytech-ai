"""User accounts and roles."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.mixins import SoftDeleteMixin, TimestampMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    FARM_OWNER = "farm_owner"
    EMPLOYEE = "employee"

    @property
    def label(self) -> str:
        return {"admin": "Admin", "farm_owner": "Farm Owner", "employee": "Employee"}[self.value]


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"), nullable=False, default=UserRole.EMPLOYEE
    )

    # Forgot-password recovery, kept local since the app runs offline on a
    # farmer's desktop with no guaranteed email/SMS delivery.
    security_question: Mapped[str] = mapped_column(String(255), nullable=False)
    security_answer_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} username={self.username!r} role={self.role.value}>"
