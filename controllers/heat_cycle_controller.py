"""Heat cycle orchestration: farm-scoped visibility/permissions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_cow_or_raise, get_farm_or_raise
from database.session import get_db_session
from models.breeding import HeatCycle
from services.cow_service import CowService
from services.farm_service import FarmService
from services.heat_cycle_service import HeatCycleService
from utils.exceptions import AppError
from utils.permissions import Permission


class HeatCycleError(AppError):
    """Raised for any heat-cycle-record failure the UI should surface."""


@dataclass(frozen=True)
class HeatCycleEntry:
    id: int
    cow_id: int
    heat_date: date
    signs: Optional[str]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class HeatCycleController(BaseController):
    def list_for_cow(self, actor: AuthenticatedUser, cow_id: int) -> List[HeatCycleEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            records = HeatCycleService(session).list_for_cow(cow_id)
            return [self._to_entry(r) for r in records]

    def create_heat_cycle(
        self,
        actor: AuthenticatedUser,
        *,
        cow_id: int,
        heat_date: date,
        signs: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> HeatCycleEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_BREEDING)

            record = HeatCycleService(session).create(
                cow_id=cow_id,
                heat_date=heat_date,
                signs=(signs.strip() or None) if signs else None,
                notes=(notes.strip() or None) if notes else None,
                recorded_by_id=actor.id,
            )
            self.logger.info("Heat cycle recorded: cow_id=%s date=%s", cow_id, heat_date)
            return self._to_entry(record)

    def update_heat_cycle(
        self,
        actor: AuthenticatedUser,
        heat_cycle_id: int,
        *,
        heat_date: date,
        signs: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> HeatCycleEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            heat_service = HeatCycleService(session)
            record = heat_service.get_by_id(heat_cycle_id)
            if record is None:
                raise HeatCycleError("Heat cycle record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, record.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_BREEDING)

            heat_service.update(
                heat_cycle_id,
                heat_date=heat_date,
                signs=(signs.strip() or None) if signs else None,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Heat cycle updated: id=%s", heat_cycle_id)
            return self._to_entry(record)

    def delete_heat_cycle(self, actor: AuthenticatedUser, heat_cycle_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            heat_service = HeatCycleService(session)
            record = heat_service.get_by_id(heat_cycle_id)
            if record is None:
                raise HeatCycleError("Heat cycle record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, record.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_BREEDING)
            heat_service.delete(heat_cycle_id)
            self.logger.info("Heat cycle deactivated: id=%s", heat_cycle_id)

    @staticmethod
    def _to_entry(record: HeatCycle) -> HeatCycleEntry:
        return HeatCycleEntry(
            id=record.id,
            cow_id=record.cow_id,
            heat_date=record.heat_date,
            signs=record.signs,
            notes=record.notes,
            recorded_by_name=record.recorded_by.full_name,
            is_active=record.is_active,
        )
