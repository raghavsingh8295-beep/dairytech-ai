"""Milk quality test results.

Kept separate from DailyRecord rather than adding columns there: quality
tests are per milking session (a farm may test morning and evening milk
separately, or just a combined sample) and aren't necessarily logged on
the same day-by-day cadence as volume, so they get their own identity
(cow, date, session) instead of piggybacking on the daily-volume record.
"""
from __future__ import annotations

import enum
from datetime import date
from typing import Optional

from sqlalchemy import Date, Float
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.cow import Cow
from models.mixins import SoftDeleteMixin, TimestampMixin
from models.user import User


class MilkSession(str, enum.Enum):
    MORNING = "morning"
    EVENING = "evening"
    COMPOSITE = "composite"

    @property
    def label(self) -> str:
        return {"morning": "Morning", "evening": "Evening", "composite": "Composite"}[self.value]


class QualityGrade(str, enum.Enum):
    A = "a"
    B = "b"
    C = "c"
    REJECTED = "rejected"

    @property
    def label(self) -> str:
        return {
            "a": "Grade A (Premium)",
            "b": "Grade B (Standard)",
            "c": "Grade C (Below Standard)",
            "rejected": "Rejected",
        }[self.value]


class MilkQualityTest(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "milk_quality_tests"
    __table_args__ = (
        UniqueConstraint("cow_id", "test_date", "session", name="uq_milk_quality_cow_date_session"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cow_id: Mapped[int] = mapped_column(ForeignKey("cows.id"), nullable=False)
    test_date: Mapped[date] = mapped_column(Date, nullable=False)
    session: Mapped[MilkSession] = mapped_column(
        SAEnum(MilkSession, name="milk_session"), nullable=False, default=MilkSession.COMPOSITE
    )

    fat_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    snf_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    protein_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    density: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bacteria_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quality_grade: Mapped[Optional[QualityGrade]] = mapped_column(
        SAEnum(QualityGrade, name="quality_grade"), nullable=True
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    cow: Mapped[Cow] = relationship("Cow", backref="milk_quality_tests")
    recorded_by: Mapped[User] = relationship("User", backref="milk_quality_tests_logged")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MilkQualityTest cow_id={self.cow_id} date={self.test_date} session={self.session.value}>"
