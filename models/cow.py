"""Cow entity and its status enums.

Pregnancy/health status here are lightweight current-state snapshots for
the cow's profile card. The full event history (AI dates, heat cycles,
treatments, vaccinations, ...) belongs to the Breeding and Health modules;
this module only owns the master record.
"""
from __future__ import annotations

import enum
from datetime import date
from typing import Optional

from sqlalchemy import Date, Float
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.farm import Farm
from models.mixins import SoftDeleteMixin, TimestampMixin


class CowGender(str, enum.Enum):
    FEMALE = "female"
    MALE = "male"

    @property
    def label(self) -> str:
        return {"female": "Female", "male": "Male"}[self.value]


class HornType(str, enum.Enum):
    HORNED = "horned"
    POLLED = "polled"
    DEHORNED = "dehorned"

    @property
    def label(self) -> str:
        return {"horned": "Horned", "polled": "Polled", "dehorned": "Dehorned"}[self.value]


class PregnancyStatus(str, enum.Enum):
    OPEN = "open"
    PREGNANT = "pregnant"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return {"open": "Open", "pregnant": "Pregnant", "unknown": "Unknown"}[self.value]


class HealthStatus(str, enum.Enum):
    HEALTHY = "healthy"
    SICK = "sick"
    UNDER_TREATMENT = "under_treatment"
    CRITICAL = "critical"
    QUARANTINED = "quarantined"

    @property
    def label(self) -> str:
        return {
            "healthy": "Healthy",
            "sick": "Sick",
            "under_treatment": "Under Treatment",
            "critical": "Critical",
            "quarantined": "Quarantined",
        }[self.value]


class Cow(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cows"
    __table_args__ = (UniqueConstraint("farm_id", "tag_number", name="uq_cow_farm_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), nullable=False)

    tag_number: Mapped[str] = mapped_column(String(30), nullable=False)
    rfid_number: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)

    photo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    qr_code_value: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    qr_code_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    breed: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[CowGender] = mapped_column(SAEnum(CowGender, name="cow_gender"), nullable=False)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    height_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    horn_type: Mapped[Optional[HornType]] = mapped_column(SAEnum(HornType, name="horn_type"), nullable=True)

    pregnancy_status: Mapped[PregnancyStatus] = mapped_column(
        SAEnum(PregnancyStatus, name="pregnancy_status"), nullable=False, default=PregnancyStatus.OPEN
    )
    expected_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    calving_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    health_status: Mapped[HealthStatus] = mapped_column(
        SAEnum(HealthStatus, name="health_status"), nullable=False, default=HealthStatus.HEALTHY
    )

    purchase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    purchase_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    farm: Mapped[Farm] = relationship("Farm", backref="cows")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Cow id={self.id} tag={self.tag_number!r}>"
