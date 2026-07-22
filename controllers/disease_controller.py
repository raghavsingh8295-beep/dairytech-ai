"""Disease orchestration: farm-scoped visibility/permissions, plus deriving
`Cow.health_status` from the cow's current disease list — this is the
"Health module owns the detailed history and keeps the snapshot in sync"
promise made back in Module 3.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_cow_or_raise, get_farm_or_raise
from database.session import get_db_session
from models.cow import HealthStatus
from models.health import Disease, DiseaseSeverity, DiseaseStatus
from services.cow_service import CowService
from services.disease_service import DiseaseService
from services.farm_service import FarmService
from utils.exceptions import AppError
from utils.permissions import Permission


class DiseaseError(AppError):
    """Raised for any disease-record failure the UI should surface."""


@dataclass(frozen=True)
class DiseaseOption:
    """A disease shown in a Treatment/DoctorVisit "related disease" dropdown."""

    id: int
    disease_name: str
    status: DiseaseStatus


@dataclass(frozen=True)
class DiseaseEntry:
    id: int
    cow_id: int
    disease_name: str
    diagnosed_date: date
    severity: DiseaseSeverity
    status: DiseaseStatus
    recovery_date: Optional[date]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class DiseaseController(BaseController):
    def list_for_cow(self, actor: AuthenticatedUser, cow_id: int) -> List[DiseaseEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            diseases = DiseaseService(session).list_for_cow(cow_id)
            return [self._to_entry(d) for d in diseases]

    def list_options_for_cow(self, actor: AuthenticatedUser, cow_id: int) -> List[DiseaseOption]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            diseases = DiseaseService(session).list_for_cow(cow_id)
            return [DiseaseOption(id=d.id, disease_name=d.disease_name, status=d.status) for d in diseases]

    def create_disease(
        self,
        actor: AuthenticatedUser,
        *,
        cow_id: int,
        disease_name: str,
        diagnosed_date: date,
        severity: DiseaseSeverity,
        status: DiseaseStatus = DiseaseStatus.ACTIVE,
        recovery_date: Optional[date] = None,
        notes: Optional[str] = None,
    ) -> DiseaseEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            disease_service = DiseaseService(session)
            cow = get_cow_or_raise(cow_service, cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_HEALTH)

            if not disease_name.strip():
                raise DiseaseError("Disease name is required.")
            recovery_date = self._resolve_recovery_date(status, recovery_date)

            disease = disease_service.create(
                cow_id=cow_id,
                disease_name=disease_name.strip(),
                diagnosed_date=diagnosed_date,
                severity=severity,
                status=status,
                recovery_date=recovery_date,
                notes=(notes.strip() or None) if notes else None,
                recorded_by_id=actor.id,
            )
            self.logger.info("Disease recorded: cow_id=%s name=%s", cow_id, disease.disease_name)
            self._sync_cow_health_status(cow_service, disease_service, cow_id)
            return self._to_entry(disease)

    def update_disease(
        self,
        actor: AuthenticatedUser,
        disease_id: int,
        *,
        disease_name: str,
        diagnosed_date: date,
        severity: DiseaseSeverity,
        status: DiseaseStatus,
        recovery_date: Optional[date] = None,
        notes: Optional[str] = None,
    ) -> DiseaseEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            disease_service = DiseaseService(session)
            disease = disease_service.get_by_id(disease_id)
            if disease is None:
                raise DiseaseError("Disease record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, disease.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_HEALTH)

            if not disease_name.strip():
                raise DiseaseError("Disease name is required.")
            recovery_date = self._resolve_recovery_date(status, recovery_date)

            disease_service.update(
                disease_id,
                disease_name=disease_name.strip(),
                diagnosed_date=diagnosed_date,
                severity=severity,
                status=status,
                recovery_date=recovery_date,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Disease updated: id=%s", disease_id)
            self._sync_cow_health_status(cow_service, disease_service, disease.cow_id)
            return self._to_entry(disease)

    def delete_disease(self, actor: AuthenticatedUser, disease_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            disease_service = DiseaseService(session)
            disease = disease_service.get_by_id(disease_id)
            if disease is None:
                raise DiseaseError("Disease record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, disease.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_HEALTH)
            disease_service.delete(disease_id)
            self.logger.info("Disease deactivated: id=%s", disease_id)
            self._sync_cow_health_status(cow_service, disease_service, disease.cow_id)

    # ---- Cow snapshot sync --------------------------------------------------

    @staticmethod
    def _sync_cow_health_status(cow_service: CowService, disease_service: DiseaseService, cow_id: int) -> None:
        """Derive Cow.health_status from the cow's currently unresolved
        diseases. Never overwrites QUARANTINED — that's a manual biosecurity
        decision independent of disease severity."""
        cow = cow_service.get_by_id(cow_id)
        if cow is None or cow.health_status == HealthStatus.QUARANTINED:
            return

        unresolved = disease_service.list_unresolved_for_cow(cow_id)
        if any(d.status == DiseaseStatus.ACTIVE and d.severity == DiseaseSeverity.SEVERE for d in unresolved):
            new_status = HealthStatus.CRITICAL
        elif any(d.status == DiseaseStatus.ACTIVE for d in unresolved):
            new_status = HealthStatus.SICK
        elif any(d.status == DiseaseStatus.RECOVERING for d in unresolved):
            new_status = HealthStatus.UNDER_TREATMENT
        else:
            new_status = HealthStatus.HEALTHY

        if cow.health_status != new_status:
            cow_service.update(cow_id, health_status=new_status)

    # ---- Validation -------------------------------------------------------

    @staticmethod
    def _resolve_recovery_date(status: DiseaseStatus, recovery_date: Optional[date]) -> Optional[date]:
        if status == DiseaseStatus.RECOVERED:
            return recovery_date or date.today()
        return None

    # ---- Mapping ------------------------------------------------------------

    @staticmethod
    def _to_entry(disease: Disease) -> DiseaseEntry:
        return DiseaseEntry(
            id=disease.id,
            cow_id=disease.cow_id,
            disease_name=disease.disease_name,
            diagnosed_date=disease.diagnosed_date,
            severity=disease.severity,
            status=disease.status,
            recovery_date=disease.recovery_date,
            notes=disease.notes,
            recorded_by_name=disease.recorded_by.full_name,
            is_active=disease.is_active,
        )
