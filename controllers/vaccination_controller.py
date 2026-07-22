"""Vaccination orchestration: farm-scoped visibility/permissions, plus the
"Automatic Reminder" feature — surfaced as an on-demand due/overdue query
rather than an OS push notification, since a desktop MVC app has no
background service to deliver one. `list_due_for_cow` is what a future
Dashboard module will call across every cow to build its "Upcoming
Vaccinations" KPI card.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_cow_or_raise, get_farm_or_raise
from database.session import get_db_session
from models.health import Vaccination
from services.cow_service import CowService
from services.farm_service import FarmService
from services.vaccination_service import VaccinationService
from utils.exceptions import AppError
from utils.permissions import Permission
from utils.validators import validate_non_negative

_DEFAULT_REMINDER_WINDOW_DAYS = 14


class VaccinationError(AppError):
    """Raised for any vaccination-record failure the UI should surface."""


@dataclass(frozen=True)
class VaccinationEntry:
    id: int
    cow_id: int
    vaccine_name: str
    scheduled_date: date
    date_given: Optional[date]
    administered_by: Optional[str]
    cost: Optional[float]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool

    @property
    def is_completed(self) -> bool:
        return self.date_given is not None

    def is_overdue(self, *, as_of: date) -> bool:
        return not self.is_completed and self.scheduled_date < as_of


class VaccinationController(BaseController):
    def list_for_cow(self, actor: AuthenticatedUser, cow_id: int) -> List[VaccinationEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            records = VaccinationService(session).list_for_cow(cow_id)
            return [self._to_entry(v) for v in records]

    def list_due_for_cow(
        self,
        actor: AuthenticatedUser,
        cow_id: int,
        *,
        within_days: int = _DEFAULT_REMINDER_WINDOW_DAYS,
        as_of: Optional[date] = None,
    ) -> List[VaccinationEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            records = VaccinationService(session).list_due_for_cow(
                cow_id, within_days=within_days, as_of=as_of or date.today()
            )
            return [self._to_entry(v) for v in records]

    def create_vaccination(
        self,
        actor: AuthenticatedUser,
        *,
        cow_id: int,
        vaccine_name: str,
        scheduled_date: date,
        date_given: Optional[date] = None,
        administered_by: Optional[str] = None,
        cost: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> VaccinationEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_HEALTH)

            self._validate_fields(vaccine_name, cost)
            vaccination = VaccinationService(session).create(
                cow_id=cow_id,
                vaccine_name=vaccine_name.strip(),
                scheduled_date=scheduled_date,
                date_given=date_given,
                administered_by=(administered_by.strip() or None) if administered_by else None,
                cost=cost,
                notes=(notes.strip() or None) if notes else None,
                recorded_by_id=actor.id,
            )
            self.logger.info("Vaccination recorded: cow_id=%s vaccine=%s", cow_id, vaccination.vaccine_name)
            return self._to_entry(vaccination)

    def update_vaccination(
        self,
        actor: AuthenticatedUser,
        vaccination_id: int,
        *,
        vaccine_name: str,
        scheduled_date: date,
        date_given: Optional[date] = None,
        administered_by: Optional[str] = None,
        cost: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> VaccinationEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            vaccination_service = VaccinationService(session)
            vaccination = vaccination_service.get_by_id(vaccination_id)
            if vaccination is None:
                raise VaccinationError("Vaccination record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, vaccination.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_HEALTH)

            self._validate_fields(vaccine_name, cost)
            vaccination_service.update(
                vaccination_id,
                vaccine_name=vaccine_name.strip(),
                scheduled_date=scheduled_date,
                date_given=date_given,
                administered_by=(administered_by.strip() or None) if administered_by else None,
                cost=cost,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Vaccination updated: id=%s", vaccination_id)
            return self._to_entry(vaccination)

    def delete_vaccination(self, actor: AuthenticatedUser, vaccination_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            vaccination_service = VaccinationService(session)
            vaccination = vaccination_service.get_by_id(vaccination_id)
            if vaccination is None:
                raise VaccinationError("Vaccination record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, vaccination.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_HEALTH)
            vaccination_service.delete(vaccination_id)
            self.logger.info("Vaccination deactivated: id=%s", vaccination_id)

    # ---- Validation -------------------------------------------------------

    @staticmethod
    def _validate_fields(vaccine_name: str, cost: Optional[float]) -> None:
        if not vaccine_name.strip():
            raise VaccinationError("Vaccine name is required.")
        if cost is not None and not validate_non_negative(cost):
            raise VaccinationError("Cost cannot be negative.")

    # ---- Mapping ------------------------------------------------------------

    @staticmethod
    def _to_entry(vaccination: Vaccination) -> VaccinationEntry:
        return VaccinationEntry(
            id=vaccination.id,
            cow_id=vaccination.cow_id,
            vaccine_name=vaccination.vaccine_name,
            scheduled_date=vaccination.scheduled_date,
            date_given=vaccination.date_given,
            administered_by=vaccination.administered_by,
            cost=vaccination.cost,
            notes=vaccination.notes,
            recorded_by_name=vaccination.recorded_by.full_name,
            is_active=vaccination.is_active,
        )
