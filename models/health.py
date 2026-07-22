"""Health module entities: diseases, vaccinations, treatments, doctor visits.

None of these are date-uniqueness-constrained per cow — a cow can have
several vaccinations, treatments, or diagnoses over its life — so unlike
DailyRecord/MilkQualityTest there is no upsert-by-date key here, just
plain CRUD rows.

`Treatment` and `DoctorVisit` may optionally reference the `Disease` they
relate to, so a disease's full history (diagnosis, visits, treatments,
recovery) can be viewed together. "Recovery History" isn't a separate
table — it's simply `Disease` rows with `status=RECOVERED`.
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
from models.cow import Cow
from models.mixins import SoftDeleteMixin, TimestampMixin
from models.user import User


class DiseaseSeverity(str, enum.Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"

    @property
    def label(self) -> str:
        return {"mild": "Mild", "moderate": "Moderate", "severe": "Severe"}[self.value]


class DiseaseStatus(str, enum.Enum):
    ACTIVE = "active"
    RECOVERING = "recovering"
    RECOVERED = "recovered"

    @property
    def label(self) -> str:
        return {"active": "Active", "recovering": "Recovering", "recovered": "Recovered"}[self.value]


class Disease(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "diseases"

    id: Mapped[int] = mapped_column(primary_key=True)
    cow_id: Mapped[int] = mapped_column(ForeignKey("cows.id"), nullable=False)

    disease_name: Mapped[str] = mapped_column(String(150), nullable=False)
    diagnosed_date: Mapped[date] = mapped_column(Date, nullable=False)
    severity: Mapped[DiseaseSeverity] = mapped_column(
        SAEnum(DiseaseSeverity, name="disease_severity"), nullable=False, default=DiseaseSeverity.MODERATE
    )
    status: Mapped[DiseaseStatus] = mapped_column(
        SAEnum(DiseaseStatus, name="disease_status"), nullable=False, default=DiseaseStatus.ACTIVE
    )
    recovery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    cow: Mapped[Cow] = relationship("Cow", backref="diseases")
    recorded_by: Mapped[User] = relationship("User", backref="diseases_logged")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Disease cow_id={self.cow_id} name={self.disease_name!r} status={self.status.value}>"


class Vaccination(Base, TimestampMixin, SoftDeleteMixin):
    """One dose/event. A future dose being scheduled is just a row with
    `date_given` still null — there's no separate "schedule" table."""

    __tablename__ = "vaccinations"

    id: Mapped[int] = mapped_column(primary_key=True)
    cow_id: Mapped[int] = mapped_column(ForeignKey("cows.id"), nullable=False)

    vaccine_name: Mapped[str] = mapped_column(String(150), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    date_given: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    administered_by: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    cow: Mapped[Cow] = relationship("Cow", backref="vaccinations")
    recorded_by: Mapped[User] = relationship("User", backref="vaccinations_logged")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vaccination cow_id={self.cow_id} vaccine={self.vaccine_name!r}>"


class Treatment(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "treatments"

    id: Mapped[int] = mapped_column(primary_key=True)
    cow_id: Mapped[int] = mapped_column(ForeignKey("cows.id"), nullable=False)
    disease_id: Mapped[Optional[int]] = mapped_column(ForeignKey("diseases.id"), nullable=True)

    medicine_name: Mapped[str] = mapped_column(String(150), nullable=False)
    dosage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    treatment_date: Mapped[date] = mapped_column(Date, nullable=False)
    administered_by: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    cow: Mapped[Cow] = relationship("Cow", backref="treatments")
    disease: Mapped[Optional[Disease]] = relationship("Disease", backref="treatments")
    recorded_by: Mapped[User] = relationship("User", backref="treatments_logged")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Treatment cow_id={self.cow_id} medicine={self.medicine_name!r}>"


class DoctorVisit(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "doctor_visits"

    id: Mapped[int] = mapped_column(primary_key=True)
    cow_id: Mapped[int] = mapped_column(ForeignKey("cows.id"), nullable=False)
    disease_id: Mapped[Optional[int]] = mapped_column(ForeignKey("diseases.id"), nullable=True)

    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    veterinarian_name: Mapped[str] = mapped_column(String(150), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    diagnosis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    cow: Mapped[Cow] = relationship("Cow", backref="doctor_visits")
    disease: Mapped[Optional[Disease]] = relationship("Disease", backref="doctor_visits")
    recorded_by: Mapped[User] = relationship("User", backref="doctor_visits_logged")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DoctorVisit cow_id={self.cow_id} vet={self.veterinarian_name!r}>"
