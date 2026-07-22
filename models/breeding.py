"""Breeding module entities: heat cycles, artificial insemination,
pregnancy tests, calf births.

Like Health, none of these are date-uniqueness-constrained per cow, so
they're plain CRUD rows. `PregnancyCheck` may reference the `Insemination`
it's confirming; `CalfBirth` may reference the `Cow` record created for
the calf once registered — "Calf Records" isn't a separate schema, a calf
is just a Cow (see `CalfBirthController.register_calf_as_cow`).
"""
from __future__ import annotations

import enum
from datetime import date
from typing import Optional

from sqlalchemy import Date, Float
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.cow import Cow, CowGender
from models.mixins import SoftDeleteMixin, TimestampMixin
from models.user import User


class PregnancyResult(str, enum.Enum):
    PREGNANT = "pregnant"
    NOT_PREGNANT = "not_pregnant"
    INCONCLUSIVE = "inconclusive"

    @property
    def label(self) -> str:
        return {
            "pregnant": "Pregnant",
            "not_pregnant": "Not Pregnant",
            "inconclusive": "Inconclusive",
        }[self.value]


class CalfOutcome(str, enum.Enum):
    ALIVE = "alive"
    STILLBORN = "stillborn"
    DIED_AFTER_BIRTH = "died_after_birth"

    @property
    def label(self) -> str:
        return {
            "alive": "Alive",
            "stillborn": "Stillborn",
            "died_after_birth": "Died After Birth",
        }[self.value]


class HeatCycle(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "heat_cycles"

    id: Mapped[int] = mapped_column(primary_key=True)
    cow_id: Mapped[int] = mapped_column(ForeignKey("cows.id"), nullable=False)

    heat_date: Mapped[date] = mapped_column(Date, nullable=False)
    signs: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    cow: Mapped[Cow] = relationship("Cow", backref="heat_cycles")
    recorded_by: Mapped[User] = relationship("User", backref="heat_cycles_logged")


class Insemination(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "inseminations"

    id: Mapped[int] = mapped_column(primary_key=True)
    cow_id: Mapped[int] = mapped_column(ForeignKey("cows.id"), nullable=False)

    insemination_date: Mapped[date] = mapped_column(Date, nullable=False)
    bull_semen_source: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    technician_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    cow: Mapped[Cow] = relationship("Cow", backref="inseminations")
    recorded_by: Mapped[User] = relationship("User", backref="inseminations_logged")


class PregnancyCheck(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "pregnancy_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    cow_id: Mapped[int] = mapped_column(ForeignKey("cows.id"), nullable=False)
    insemination_id: Mapped[Optional[int]] = mapped_column(ForeignKey("inseminations.id"), nullable=True)

    check_date: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    result: Mapped[PregnancyResult] = mapped_column(
        SAEnum(PregnancyResult, name="pregnancy_result"), nullable=False
    )
    expected_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    performed_by: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    cow: Mapped[Cow] = relationship("Cow", backref="pregnancy_checks")
    insemination: Mapped[Optional[Insemination]] = relationship("Insemination", backref="pregnancy_checks")
    recorded_by: Mapped[User] = relationship("User", backref="pregnancy_checks_logged")


class CalfBirth(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "calf_births"

    id: Mapped[int] = mapped_column(primary_key=True)
    mother_cow_id: Mapped[int] = mapped_column(ForeignKey("cows.id"), nullable=False)
    calf_cow_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cows.id"), nullable=True)

    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    calf_gender: Mapped[CowGender] = mapped_column(SAEnum(CowGender, name="calf_gender"), nullable=False)
    outcome: Mapped[CalfOutcome] = mapped_column(
        SAEnum(CalfOutcome, name="calf_outcome"), nullable=False, default=CalfOutcome.ALIVE
    )
    birth_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    complications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    mother: Mapped[Cow] = relationship("Cow", foreign_keys=[mother_cow_id], backref="calf_births")
    calf_cow: Mapped[Optional[Cow]] = relationship("Cow", foreign_keys=[calf_cow_id])
    recorded_by: Mapped[User] = relationship("User", backref="calf_births_logged")
