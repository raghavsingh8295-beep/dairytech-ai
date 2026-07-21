"""Daily recording orchestration: farm-scoped visibility (via the cow's
farm), upsert-by-date semantics, and syncing the latest weight/pregnancy
observation back onto the Cow profile snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_farm_or_raise
from database.session import get_db_session
from models.cow import Cow, PregnancyStatus
from models.daily_record import DailyRecord
from services.cow_service import CowService
from services.daily_record_service import DailyRecordService
from services.farm_service import FarmService
from utils.exceptions import AppError
from utils.permissions import Permission
from utils.validators import validate_non_negative


class DailyRecordError(AppError):
    """Raised for any daily-recording failure the UI should surface."""


@dataclass(frozen=True)
class DailyRecordEntry:
    id: int
    cow_id: int
    record_date: date
    milk_morning_liters: Optional[float]
    milk_evening_liters: Optional[float]
    total_milk_liters: Optional[float]
    weight_kg: Optional[float]
    body_temperature_c: Optional[float]
    heart_rate_bpm: Optional[int]
    rumination_minutes: Optional[float]
    activity_level: Optional[float]
    feed_intake_kg: Optional[float]
    water_intake_liters: Optional[float]
    medicine_given: Optional[str]
    vaccination_given: Optional[str]
    disease_note: Optional[str]
    pregnancy_status: Optional[PregnancyStatus]
    heat_detected: bool
    body_condition_score: Optional[float]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class DailyRecordController(BaseController):
    def list_for_cow(
        self,
        actor: AuthenticatedUser,
        cow_id: int,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> List[DailyRecordEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = self._require_cow(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            records = DailyRecordService(session).list_for_cow(
                cow_id, start_date=start_date, end_date=end_date, limit=limit
            )
            return [self._to_entry(r) for r in records]

    def get_for_date(
        self, actor: AuthenticatedUser, cow_id: int, record_date: date
    ) -> Optional[DailyRecordEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = self._require_cow(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            record = DailyRecordService(session).get_for_cow_and_date(cow_id, record_date)
            return self._to_entry(record) if record is not None else None

    def save_record(
        self,
        actor: AuthenticatedUser,
        *,
        cow_id: int,
        record_date: date,
        milk_morning_liters: Optional[float] = None,
        milk_evening_liters: Optional[float] = None,
        weight_kg: Optional[float] = None,
        body_temperature_c: Optional[float] = None,
        heart_rate_bpm: Optional[int] = None,
        rumination_minutes: Optional[float] = None,
        activity_level: Optional[float] = None,
        feed_intake_kg: Optional[float] = None,
        water_intake_liters: Optional[float] = None,
        medicine_given: Optional[str] = None,
        vaccination_given: Optional[str] = None,
        disease_note: Optional[str] = None,
        pregnancy_status: Optional[PregnancyStatus] = None,
        heat_detected: bool = False,
        body_condition_score: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> DailyRecordEntry:
        """Create today's (or a backdated) entry, or update it in place if one
        already exists for this cow on this date.

        The update path is a full overwrite, not a partial patch: every
        field's current value (including `None`) is written as given.
        Callers that might be updating an existing date must pass the
        record's complete current state, not just the fields they changed
        — otherwise unspecified fields are silently cleared. `DailyRecordFormDialog`
        handles this by always resolving and repopulating from any existing
        record before submitting; a future caller (bulk import, AI
        auto-logging, ...) must do the same via `get_for_date` first.
        """
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            daily_service = DailyRecordService(session)
            cow = self._require_cow(cow_service, cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(
                farm_service, actor, farm, required_permission=Permission.RECORD_DAILY_DATA
            )

            fields = dict(
                milk_morning_liters=milk_morning_liters,
                milk_evening_liters=milk_evening_liters,
                weight_kg=weight_kg,
                body_temperature_c=body_temperature_c,
                heart_rate_bpm=heart_rate_bpm,
                rumination_minutes=rumination_minutes,
                activity_level=activity_level,
                feed_intake_kg=feed_intake_kg,
                water_intake_liters=water_intake_liters,
                medicine_given=(medicine_given.strip() or None) if medicine_given else None,
                vaccination_given=(vaccination_given.strip() or None) if vaccination_given else None,
                disease_note=(disease_note.strip() or None) if disease_note else None,
                pregnancy_status=pregnancy_status,
                heat_detected=heat_detected,
                body_condition_score=body_condition_score,
                notes=(notes.strip() or None) if notes else None,
            )
            self._validate_fields(fields)

            existing = daily_service.get_for_cow_and_date(cow_id, record_date)
            if existing is None:
                record = daily_service.create(
                    cow_id=cow_id, record_date=record_date, recorded_by_id=actor.id, **fields
                )
                self.logger.info("Daily record created: cow_id=%s date=%s", cow_id, record_date)
            else:
                record = daily_service.update(existing.id, **fields)
                self.logger.info("Daily record updated: cow_id=%s date=%s", cow_id, record_date)

            self._sync_cow_snapshot(cow_service, daily_service, cow_id, record_date, weight_kg, pregnancy_status)

            return self._to_entry(record)

    def delete_record(self, actor: AuthenticatedUser, record_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            daily_service = DailyRecordService(session)
            record = daily_service.get_by_id(record_id)
            if record is None:
                raise DailyRecordError("Record not found.")
            cow = self._require_cow(CowService(session), record.cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(
                farm_service, actor, farm, required_permission=Permission.RECORD_DAILY_DATA
            )
            daily_service.delete(record_id)
            self.logger.info("Daily record deactivated: id=%s", record_id)

    # ---- Sync -----------------------------------------------------------

    @staticmethod
    def _sync_cow_snapshot(
        cow_service: CowService,
        daily_service: DailyRecordService,
        cow_id: int,
        record_date: date,
        weight_kg: Optional[float],
        pregnancy_status: Optional[PregnancyStatus],
    ) -> None:
        """If this is the most recent record for the cow, refresh the
        profile's reference weight/pregnancy status to match."""
        if weight_kg is None and pregnancy_status is None:
            return
        latest_date = daily_service.latest_record_date(cow_id)
        if latest_date is not None and record_date < latest_date:
            return
        updates = {}
        if weight_kg is not None:
            updates["weight_kg"] = weight_kg
        if pregnancy_status is not None:
            updates["pregnancy_status"] = pregnancy_status
        if updates:
            cow_service.update(cow_id, **updates)

    # ---- Validation -------------------------------------------------------

    @staticmethod
    def _validate_fields(fields: dict) -> None:
        for key in (
            "milk_morning_liters",
            "milk_evening_liters",
            "weight_kg",
            "feed_intake_kg",
            "water_intake_liters",
            "rumination_minutes",
            "activity_level",
        ):
            value = fields.get(key)
            if value is not None and not validate_non_negative(value):
                raise DailyRecordError(f"{key.replace('_', ' ').capitalize()} cannot be negative.")

        heart_rate = fields.get("heart_rate_bpm")
        if heart_rate is not None and heart_rate < 0:
            raise DailyRecordError("Heart rate cannot be negative.")

        temperature = fields.get("body_temperature_c")
        if temperature is not None and not (30.0 <= temperature <= 45.0):
            raise DailyRecordError("Body temperature must be between 30 and 45 °C.")

        bcs = fields.get("body_condition_score")
        if bcs is not None and not (1.0 <= bcs <= 5.0):
            raise DailyRecordError("Body condition score must be between 1 and 5.")

    @staticmethod
    def _require_cow(cow_service: CowService, cow_id: int) -> Cow:
        cow = cow_service.get_by_id(cow_id)
        if cow is None:
            raise DailyRecordError("Cow not found.")
        return cow

    # ---- Mapping ------------------------------------------------------------

    @staticmethod
    def _to_entry(record: DailyRecord) -> DailyRecordEntry:
        morning = record.milk_morning_liters
        evening = record.milk_evening_liters
        total = None if morning is None and evening is None else (morning or 0) + (evening or 0)
        return DailyRecordEntry(
            id=record.id,
            cow_id=record.cow_id,
            record_date=record.record_date,
            milk_morning_liters=morning,
            milk_evening_liters=evening,
            total_milk_liters=total,
            weight_kg=record.weight_kg,
            body_temperature_c=record.body_temperature_c,
            heart_rate_bpm=record.heart_rate_bpm,
            rumination_minutes=record.rumination_minutes,
            activity_level=record.activity_level,
            feed_intake_kg=record.feed_intake_kg,
            water_intake_liters=record.water_intake_liters,
            medicine_given=record.medicine_given,
            vaccination_given=record.vaccination_given,
            disease_note=record.disease_note,
            pregnancy_status=record.pregnancy_status,
            heat_detected=record.heat_detected,
            body_condition_score=record.body_condition_score,
            notes=record.notes,
            recorded_by_name=record.recorded_by.full_name,
            is_active=record.is_active,
        )
