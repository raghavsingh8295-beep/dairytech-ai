"""Doctor visit orchestration: farm-scoped visibility/permissions, plus
follow-up-date reminders (same on-demand approach as vaccination due dates)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_cow_or_raise, get_farm_or_raise
from database.session import get_db_session
from models.health import DoctorVisit
from services.cow_service import CowService
from services.doctor_visit_service import DoctorVisitService
from services.farm_service import FarmService
from utils.exceptions import AppError
from utils.permissions import Permission
from utils.validators import validate_non_negative

_DEFAULT_REMINDER_WINDOW_DAYS = 14


class DoctorVisitError(AppError):
    """Raised for any doctor-visit-record failure the UI should surface."""


@dataclass(frozen=True)
class DoctorVisitEntry:
    id: int
    cow_id: int
    disease_id: Optional[int]
    visit_date: date
    veterinarian_name: str
    reason: Optional[str]
    diagnosis: Optional[str]
    recommendations: Optional[str]
    follow_up_date: Optional[date]
    cost: Optional[float]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class DoctorVisitController(BaseController):
    def list_for_cow(self, actor: AuthenticatedUser, cow_id: int) -> List[DoctorVisitEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            records = DoctorVisitService(session).list_for_cow(cow_id)
            return [self._to_entry(v) for v in records]

    def list_upcoming_follow_ups_for_cow(
        self,
        actor: AuthenticatedUser,
        cow_id: int,
        *,
        within_days: int = _DEFAULT_REMINDER_WINDOW_DAYS,
        as_of: Optional[date] = None,
    ) -> List[DoctorVisitEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            records = DoctorVisitService(session).list_upcoming_follow_ups_for_cow(
                cow_id, within_days=within_days, as_of=as_of or date.today()
            )
            return [self._to_entry(v) for v in records]

    def create_visit(
        self,
        actor: AuthenticatedUser,
        *,
        cow_id: int,
        veterinarian_name: str,
        visit_date: date,
        disease_id: Optional[int] = None,
        reason: Optional[str] = None,
        diagnosis: Optional[str] = None,
        recommendations: Optional[str] = None,
        follow_up_date: Optional[date] = None,
        cost: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> DoctorVisitEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_HEALTH)

            self._validate_fields(veterinarian_name, cost)
            visit = DoctorVisitService(session).create(
                cow_id=cow_id,
                disease_id=disease_id,
                visit_date=visit_date,
                veterinarian_name=veterinarian_name.strip(),
                reason=(reason.strip() or None) if reason else None,
                diagnosis=(diagnosis.strip() or None) if diagnosis else None,
                recommendations=(recommendations.strip() or None) if recommendations else None,
                follow_up_date=follow_up_date,
                cost=cost,
                notes=(notes.strip() or None) if notes else None,
                recorded_by_id=actor.id,
            )
            self.logger.info("Doctor visit recorded: cow_id=%s vet=%s", cow_id, visit.veterinarian_name)
            return self._to_entry(visit)

    def update_visit(
        self,
        actor: AuthenticatedUser,
        visit_id: int,
        *,
        veterinarian_name: str,
        visit_date: date,
        disease_id: Optional[int] = None,
        reason: Optional[str] = None,
        diagnosis: Optional[str] = None,
        recommendations: Optional[str] = None,
        follow_up_date: Optional[date] = None,
        cost: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> DoctorVisitEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            visit_service = DoctorVisitService(session)
            visit = visit_service.get_by_id(visit_id)
            if visit is None:
                raise DoctorVisitError("Doctor visit record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, visit.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_HEALTH)

            self._validate_fields(veterinarian_name, cost)
            visit_service.update(
                visit_id,
                disease_id=disease_id,
                visit_date=visit_date,
                veterinarian_name=veterinarian_name.strip(),
                reason=(reason.strip() or None) if reason else None,
                diagnosis=(diagnosis.strip() or None) if diagnosis else None,
                recommendations=(recommendations.strip() or None) if recommendations else None,
                follow_up_date=follow_up_date,
                cost=cost,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Doctor visit updated: id=%s", visit_id)
            return self._to_entry(visit)

    def delete_visit(self, actor: AuthenticatedUser, visit_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            visit_service = DoctorVisitService(session)
            visit = visit_service.get_by_id(visit_id)
            if visit is None:
                raise DoctorVisitError("Doctor visit record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, visit.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_HEALTH)
            visit_service.delete(visit_id)
            self.logger.info("Doctor visit deactivated: id=%s", visit_id)

    # ---- Validation -------------------------------------------------------

    @staticmethod
    def _validate_fields(veterinarian_name: str, cost: Optional[float]) -> None:
        if not veterinarian_name.strip():
            raise DoctorVisitError("Veterinarian name is required.")
        if cost is not None and not validate_non_negative(cost):
            raise DoctorVisitError("Cost cannot be negative.")

    # ---- Mapping ------------------------------------------------------------

    @staticmethod
    def _to_entry(visit: DoctorVisit) -> DoctorVisitEntry:
        return DoctorVisitEntry(
            id=visit.id,
            cow_id=visit.cow_id,
            disease_id=visit.disease_id,
            visit_date=visit.visit_date,
            veterinarian_name=visit.veterinarian_name,
            reason=visit.reason,
            diagnosis=visit.diagnosis,
            recommendations=visit.recommendations,
            follow_up_date=visit.follow_up_date,
            cost=visit.cost,
            notes=visit.notes,
            recorded_by_name=visit.recorded_by.full_name,
            is_active=visit.is_active,
        )
