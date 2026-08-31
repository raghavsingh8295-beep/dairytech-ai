"""One record per cow per day.

Medicine/vaccination/disease fields here are lightweight same-day notes,
not the structured, scheduled records the Health module will own — this
module exists so a farmer can log "gave antibiotics today" in passing
without leaving the daily-entry screen.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer
from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.cow import Cow, PregnancyStatus
from models.mixins import SoftDeleteMixin, TimestampMixin
from models.user import User


class DailyRecord(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "daily_records"
    __table_args__ = (UniqueConstraint("cow_id", "record_date", name="uq_daily_record_cow_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cow_id: Mapped[int] = mapped_column(ForeignKey("cows.id"), nullable=False)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)

    milk_morning_liters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    milk_evening_liters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    body_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    heart_rate_bpm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rumination_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    activity_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feed_intake_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    water_intake_liters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    medicine_given: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vaccination_given: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    disease_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    pregnancy_status: Mapped[Optional[PregnancyStatus]] = mapped_column(
        SAEnum(PregnancyStatus, name="daily_pregnancy_status"), nullable=True
    )
    heat_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    body_condition_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Once true, the (cow, date) slot is locked: `save_record`'s upsert and
    # `delete_record` both refuse to touch it. One-way by design — this
    # exists so a farmer can mark a day's entry final (after the evening
    # milking, say) so it can't be silently changed later, not so it can be
    # toggled back and forth.
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    cow: Mapped[Cow] = relationship("Cow", backref="daily_records")
    recorded_by: Mapped[User] = relationship("User", backref="daily_records_logged")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DailyRecord cow_id={self.cow_id} date={self.record_date}>"
