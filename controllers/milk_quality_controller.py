"""Milk quality orchestration: farm-scoped visibility (via the cow's farm,
same as Daily Recording), upsert-by-(date, session), and a grade-suggestion
heuristic the UI can offer before the farmer commits to a value.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_cow_or_raise, get_farm_or_raise
from database.session import get_db_session
from models.milk_quality import MilkQualityTest, MilkSession, QualityGrade
from services.cow_service import CowService
from services.farm_service import FarmService
from services.milk_quality_service import MilkQualityService
from utils.exceptions import AppError
from utils.permissions import Permission


class MilkQualityError(AppError):
    """Raised for any milk-quality-related failure the UI should surface."""


@dataclass(frozen=True)
class MilkQualityEntry:
    id: int
    cow_id: int
    test_date: date
    session: MilkSession
    fat_percent: Optional[float]
    snf_percent: Optional[float]
    protein_percent: Optional[float]
    density: Optional[float]
    bacteria_count: Optional[int]
    quality_grade: Optional[QualityGrade]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class MilkQualityController(BaseController):
    def list_for_cow(
        self,
        actor: AuthenticatedUser,
        cow_id: int,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> List[MilkQualityEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            tests = MilkQualityService(session).list_for_cow(
                cow_id, start_date=start_date, end_date=end_date, limit=limit
            )
            return [self._to_entry(t) for t in tests]

    def get_for_date_session(
        self, actor: AuthenticatedUser, cow_id: int, test_date: date, session_type: MilkSession
    ) -> Optional[MilkQualityEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            test = MilkQualityService(session).get_for_cow_date_session(cow_id, test_date, session_type)
            return self._to_entry(test) if test is not None else None

    def save_test(
        self,
        actor: AuthenticatedUser,
        *,
        cow_id: int,
        test_date: date,
        session_type: MilkSession,
        fat_percent: Optional[float] = None,
        snf_percent: Optional[float] = None,
        protein_percent: Optional[float] = None,
        density: Optional[float] = None,
        bacteria_count: Optional[int] = None,
        quality_grade: Optional[QualityGrade] = None,
        notes: Optional[str] = None,
    ) -> MilkQualityEntry:
        """Create or update the test for (cow, test_date, session_type).

        Like Daily Recording, this is a full-overwrite upsert, not a
        partial patch — a caller resuming an existing test must pass its
        complete current state (see `MilkQualityFormDialog`), or fields it
        omits will be cleared.
        """
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            quality_service = MilkQualityService(session)
            cow = get_cow_or_raise(cow_service, cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(
                farm_service, actor, farm, required_permission=Permission.RECORD_DAILY_DATA
            )

            fields = dict(
                fat_percent=fat_percent,
                snf_percent=snf_percent,
                protein_percent=protein_percent,
                density=density,
                bacteria_count=bacteria_count,
                quality_grade=quality_grade,
                notes=(notes.strip() or None) if notes else None,
            )
            self._validate_fields(fields)

            existing = quality_service.get_any_for_cow_date_session(cow_id, test_date, session_type)
            if existing is None:
                test = quality_service.create(
                    cow_id=cow_id,
                    test_date=test_date,
                    session=session_type,
                    recorded_by_id=actor.id,
                    **fields,
                )
                self.logger.info(
                    "Milk quality test created: cow_id=%s date=%s session=%s",
                    cow_id,
                    test_date,
                    session_type.value,
                )
            else:
                # `existing` may be a soft-deleted row occupying this
                # (cow, date, session) slot — reviving it on save matches
                # the "save = the current state for this slot" contract.
                test = quality_service.update(existing.id, is_active=True, **fields)
                self.logger.info(
                    "Milk quality test updated: cow_id=%s date=%s session=%s",
                    cow_id,
                    test_date,
                    session_type.value,
                )

            return self._to_entry(test)

    def delete_test(self, actor: AuthenticatedUser, test_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            quality_service = MilkQualityService(session)
            test = quality_service.get_by_id(test_id)
            if test is None:
                raise MilkQualityError("Test not found.")
            cow = get_cow_or_raise(CowService(session), test.cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(
                farm_service, actor, farm, required_permission=Permission.RECORD_DAILY_DATA
            )
            quality_service.delete(test_id)
            self.logger.info("Milk quality test deactivated: id=%s", test_id)

    # ---- Grading heuristic --------------------------------------------------

    @staticmethod
    def suggest_grade(
        fat_percent: Optional[float], snf_percent: Optional[float], bacteria_count: Optional[int]
    ) -> Optional[QualityGrade]:
        """A simple, adjustable heuristic for suggesting a grade from raw
        metrics — not a regulatory standard. Real grading cutoffs vary by
        country/co-op; this is a starting point the farmer can override.
        """
        if fat_percent is None or snf_percent is None or bacteria_count is None:
            return None
        if fat_percent < 2.5 or bacteria_count > 4_000_000:
            return QualityGrade.REJECTED
        if fat_percent >= 4.0 and snf_percent >= 8.5 and bacteria_count <= 200_000:
            return QualityGrade.A
        if fat_percent >= 3.5 and snf_percent >= 8.0 and bacteria_count <= 1_000_000:
            return QualityGrade.B
        return QualityGrade.C

    # ---- Validation -------------------------------------------------------

    @staticmethod
    def _validate_fields(fields: dict) -> None:
        fat = fields.get("fat_percent")
        if fat is not None and not (0.0 <= fat <= 15.0):
            raise MilkQualityError("Fat % must be between 0 and 15.")

        snf = fields.get("snf_percent")
        if snf is not None and not (0.0 <= snf <= 15.0):
            raise MilkQualityError("SNF % must be between 0 and 15.")

        protein = fields.get("protein_percent")
        if protein is not None and not (0.0 <= protein <= 10.0):
            raise MilkQualityError("Protein % must be between 0 and 10.")

        density = fields.get("density")
        if density is not None and not (900.0 <= density <= 1100.0):
            raise MilkQualityError("Density must be between 900 and 1100 kg/m³.")

        bacteria = fields.get("bacteria_count")
        if bacteria is not None and bacteria < 0:
            raise MilkQualityError("Bacteria count cannot be negative.")

    # ---- Mapping ------------------------------------------------------------

    @staticmethod
    def _to_entry(test: MilkQualityTest) -> MilkQualityEntry:
        return MilkQualityEntry(
            id=test.id,
            cow_id=test.cow_id,
            test_date=test.test_date,
            session=test.session,
            fat_percent=test.fat_percent,
            snf_percent=test.snf_percent,
            protein_percent=test.protein_percent,
            density=test.density,
            bacteria_count=test.bacteria_count,
            quality_grade=test.quality_grade,
            notes=test.notes,
            recorded_by_name=test.recorded_by.full_name,
            is_active=test.is_active,
        )
