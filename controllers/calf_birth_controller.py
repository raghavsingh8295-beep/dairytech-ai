"""Calf birth orchestration: farm-scoped visibility/permissions, syncing
the mother's pregnancy snapshot on birth, and linking a birth record to
the `Cow` created for the calf. "Calf Records" isn't a separate schema —
a calf is a Cow, registered through the same Cow Management module built
in Module 3 (see `link_calf_cow`, called after `CowController.create_cow`
succeeds from the calf-birth screen).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_cow_or_raise, get_farm_or_raise
from database.session import get_db_session
from models.breeding import CalfBirth, CalfOutcome
from models.cow import CowGender, PregnancyStatus
from services.calf_birth_service import CalfBirthService
from services.cow_service import CowService
from services.farm_service import FarmService
from utils.exceptions import AppError
from utils.permissions import Permission
from utils.validators import validate_non_negative


class CalfBirthError(AppError):
    """Raised for any calf-birth-record failure the UI should surface."""


@dataclass(frozen=True)
class CalfBirthEntry:
    id: int
    mother_cow_id: int
    calf_cow_id: Optional[int]
    birth_date: date
    calf_gender: CowGender
    outcome: CalfOutcome
    birth_weight_kg: Optional[float]
    complications: Optional[str]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class CalfBirthController(BaseController):
    def list_for_mother(self, actor: AuthenticatedUser, mother_cow_id: int) -> List[CalfBirthEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), mother_cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            records = CalfBirthService(session).list_for_mother(mother_cow_id)
            return [self._to_entry(r) for r in records]

    def create_birth(
        self,
        actor: AuthenticatedUser,
        *,
        mother_cow_id: int,
        birth_date: date,
        calf_gender: CowGender,
        outcome: CalfOutcome = CalfOutcome.ALIVE,
        birth_weight_kg: Optional[float] = None,
        complications: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> CalfBirthEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            birth_service = CalfBirthService(session)
            mother = get_cow_or_raise(cow_service, mother_cow_id)
            farm = get_farm_or_raise(farm_service, mother.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_BREEDING)

            if birth_weight_kg is not None and not validate_non_negative(birth_weight_kg):
                raise CalfBirthError("Birth weight cannot be negative.")

            record = birth_service.create(
                mother_cow_id=mother_cow_id,
                calf_cow_id=None,
                birth_date=birth_date,
                calf_gender=calf_gender,
                outcome=outcome,
                birth_weight_kg=birth_weight_kg,
                complications=(complications.strip() or None) if complications else None,
                notes=(notes.strip() or None) if notes else None,
                recorded_by_id=actor.id,
            )
            self.logger.info("Calf birth recorded: mother_cow_id=%s date=%s", mother_cow_id, birth_date)

            # A birth is definitive ground truth: the mother is no longer
            # pregnant, regardless of what any prior pregnancy test said.
            cow_service.update(
                mother_cow_id, pregnancy_status=PregnancyStatus.OPEN, expected_delivery_date=None
            )
            return self._to_entry(record)

    def update_birth(
        self,
        actor: AuthenticatedUser,
        birth_id: int,
        *,
        birth_date: date,
        calf_gender: CowGender,
        outcome: CalfOutcome,
        birth_weight_kg: Optional[float] = None,
        complications: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> CalfBirthEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            birth_service = CalfBirthService(session)
            record = birth_service.get_by_id(birth_id)
            if record is None:
                raise CalfBirthError("Calf birth record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, record.mother_cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_BREEDING)

            if birth_weight_kg is not None and not validate_non_negative(birth_weight_kg):
                raise CalfBirthError("Birth weight cannot be negative.")

            birth_service.update(
                birth_id,
                birth_date=birth_date,
                calf_gender=calf_gender,
                outcome=outcome,
                birth_weight_kg=birth_weight_kg,
                complications=(complications.strip() or None) if complications else None,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Calf birth updated: id=%s", birth_id)
            return self._to_entry(record)

    def delete_birth(self, actor: AuthenticatedUser, birth_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            birth_service = CalfBirthService(session)
            record = birth_service.get_by_id(birth_id)
            if record is None:
                raise CalfBirthError("Calf birth record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, record.mother_cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_BREEDING)
            birth_service.delete(birth_id)
            self.logger.info("Calf birth deactivated: id=%s", birth_id)

    def link_calf_cow(self, actor: AuthenticatedUser, birth_id: int, calf_cow_id: int) -> CalfBirthEntry:
        """Attach the just-created Cow record for this calf to its birth event."""
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            birth_service = CalfBirthService(session)
            record = birth_service.get_by_id(birth_id)
            if record is None:
                raise CalfBirthError("Calf birth record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, record.mother_cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_BREEDING)

            if record.calf_cow_id is not None:
                raise CalfBirthError("This birth is already linked to a cow record.")
            get_cow_or_raise(cow_service, calf_cow_id)  # ensure the target cow exists

            birth_service.update(birth_id, calf_cow_id=calf_cow_id)
            self.logger.info("Calf birth id=%s linked to cow_id=%s", birth_id, calf_cow_id)
            return self._to_entry(record)

    @staticmethod
    def _to_entry(record: CalfBirth) -> CalfBirthEntry:
        return CalfBirthEntry(
            id=record.id,
            mother_cow_id=record.mother_cow_id,
            calf_cow_id=record.calf_cow_id,
            birth_date=record.birth_date,
            calf_gender=record.calf_gender,
            outcome=record.outcome,
            birth_weight_kg=record.birth_weight_kg,
            complications=record.complications,
            notes=record.notes,
            recorded_by_name=record.recorded_by.full_name,
            is_active=record.is_active,
        )
