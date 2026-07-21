"""Farm entity and farm-employee assignment."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.mixins import SoftDeleteMixin, TimestampMixin
from models.user import User


class Farm(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "farms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gps_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    photo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # backref (instead of back_populates) so models/user.py — owned by
    # Module 1 — never needs to change when Module 2 adds this relationship.
    owner: Mapped[User] = relationship("User", backref="owned_farms", foreign_keys=[owner_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Farm id={self.id} name={self.name!r}>"


class FarmEmployee(Base, TimestampMixin):
    """Many-to-many assignment of an Employee-role user to a farm.

    A join table (rather than a `farm_id` column on User) avoids a circular
    foreign key between `users` and `farms` — SQLite handles a table that
    references both far more reliably than two tables that reference each
    other — and lets an employee be assigned to more than one farm.
    """

    __tablename__ = "farm_employees"
    __table_args__ = (UniqueConstraint("farm_id", "user_id", name="uq_farm_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    farm: Mapped[Farm] = relationship("Farm", backref="employee_links")
    user: Mapped[User] = relationship("User", backref="farm_employee_links")
