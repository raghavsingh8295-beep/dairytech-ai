"""Artificial insemination orchestration: farm-scoped visibility/permissions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_cow_or_raise, get_farm_or_raise
from database.session import get_db_session
from models.breeding import Insemination
from services.cow_service import CowService
from services.farm_service import FarmService
from services.insemination_service import InseminationService
from utils.exceptions import AppError
from utils.permissions import Permission
from utils.validators import validate_non_negative


class InseminationError(AppError):
    """Raised for any insemination-record failure the UI should surface."""


@dataclass(frozen=True)
class InseminationEntry:
    id: int
    cow_id: int
    insemination_date: date
    bull_semen_source: Optional[str]
    technician_name: Optional[str]
    cost: Optional[float]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class InseminationController(BaseController):
    def list_for_cow(self, actor: AuthenticatedUser, cow_id: int) -> List[InseminationEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            records = InseminationService(session).list_for_cow(cow_id)
            return [self._to_entry(r) for r in records]

    def create_insemination(
        self,
        actor: AuthenticatedUser,
        *,
        cow_id: int,
        insemination_date: date,
        bull_semen_source: Optional[str] = None,
        technician_name: Optional[str] = None,
        cost: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> InseminationEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_BREEDING)

            self._validate_cost(cost)
            record = InseminationService(session).create(
                cow_id=cow_id,
                insemination_date=insemination_date,
                bull_semen_source=(bull_semen_source.strip() or None) if bull_semen_source else None,
                technician_name=(technician_name.strip() or None) if technician_name else None,
                cost=cost,
                notes=(notes.strip() or None) if notes else None,
                recorded_by_id=actor.id,
            )
            self.logger.info("Insemination recorded: cow_id=%s date=%s", cow_id, insemination_date)
            return self._to_entry(record)

    def update_insemination(
        self,
        actor: AuthenticatedUser,
        insemination_id: int,
        *,
        insemination_date: date,
        bull_semen_source: Optional[str] = None,
        technician_name: Optional[str] = None,
        cost: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> InseminationEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            insemination_service = InseminationService(session)
            record = insemination_service.get_by_id(insemination_id)
            if record is None:
                raise InseminationError("Insemination record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, record.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_BREEDING)

            self._validate_cost(cost)
            insemination_service.update(
                insemination_id,
                insemination_date=insemination_date,
                bull_semen_source=(bull_semen_source.strip() or None) if bull_semen_source else None,
                technician_name=(technician_name.strip() or None) if technician_name else None,
                cost=cost,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Insemination updated: id=%s", insemination_id)
            return self._to_entry(record)

    def delete_insemination(self, actor: AuthenticatedUser, insemination_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            insemination_service = InseminationService(session)
            record = insemination_service.get_by_id(insemination_id)
            if record is None:
                raise InseminationError("Insemination record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, record.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_BREEDING)
            insemination_service.delete(insemination_id)
            self.logger.info("Insemination deactivated: id=%s", insemination_id)

    @staticmethod
    def _validate_cost(cost: Optional[float]) -> None:
        if cost is not None and not validate_non_negative(cost):
            raise InseminationError("Cost cannot be negative.")

    @staticmethod
    def _to_entry(record: Insemination) -> InseminationEntry:
        return InseminationEntry(
            id=record.id,
            cow_id=record.cow_id,
            insemination_date=record.insemination_date,
            bull_semen_source=record.bull_semen_source,
            technician_name=record.technician_name,
            cost=record.cost,
            notes=record.notes,
            recorded_by_name=record.recorded_by.full_name,
            is_active=record.is_active,
        )
