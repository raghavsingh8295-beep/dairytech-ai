"""Treatment (medicine record) orchestration: farm-scoped visibility/permissions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_cow_or_raise, get_farm_or_raise
from database.session import get_db_session
from models.health import Treatment
from services.cow_service import CowService
from services.farm_service import FarmService
from services.treatment_service import TreatmentService
from utils.exceptions import AppError
from utils.permissions import Permission
from utils.validators import validate_non_negative


class TreatmentError(AppError):
    """Raised for any treatment-record failure the UI should surface."""


@dataclass(frozen=True)
class TreatmentEntry:
    id: int
    cow_id: int
    disease_id: Optional[int]
    medicine_name: str
    dosage: Optional[str]
    treatment_date: date
    administered_by: Optional[str]
    cost: Optional[float]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class TreatmentController(BaseController):
    def list_for_cow(self, actor: AuthenticatedUser, cow_id: int) -> List[TreatmentEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            records = TreatmentService(session).list_for_cow(cow_id)
            return [self._to_entry(t) for t in records]

    def create_treatment(
        self,
        actor: AuthenticatedUser,
        *,
        cow_id: int,
        medicine_name: str,
        treatment_date: date,
        disease_id: Optional[int] = None,
        dosage: Optional[str] = None,
        administered_by: Optional[str] = None,
        cost: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> TreatmentEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_HEALTH)

            self._validate_fields(medicine_name, cost)
            treatment = TreatmentService(session).create(
                cow_id=cow_id,
                disease_id=disease_id,
                medicine_name=medicine_name.strip(),
                dosage=(dosage.strip() or None) if dosage else None,
                treatment_date=treatment_date,
                administered_by=(administered_by.strip() or None) if administered_by else None,
                cost=cost,
                notes=(notes.strip() or None) if notes else None,
                recorded_by_id=actor.id,
            )
            self.logger.info("Treatment recorded: cow_id=%s medicine=%s", cow_id, treatment.medicine_name)
            return self._to_entry(treatment)

    def update_treatment(
        self,
        actor: AuthenticatedUser,
        treatment_id: int,
        *,
        medicine_name: str,
        treatment_date: date,
        disease_id: Optional[int] = None,
        dosage: Optional[str] = None,
        administered_by: Optional[str] = None,
        cost: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> TreatmentEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            treatment_service = TreatmentService(session)
            treatment = treatment_service.get_by_id(treatment_id)
            if treatment is None:
                raise TreatmentError("Treatment record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, treatment.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_HEALTH)

            self._validate_fields(medicine_name, cost)
            treatment_service.update(
                treatment_id,
                disease_id=disease_id,
                medicine_name=medicine_name.strip(),
                dosage=(dosage.strip() or None) if dosage else None,
                treatment_date=treatment_date,
                administered_by=(administered_by.strip() or None) if administered_by else None,
                cost=cost,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Treatment updated: id=%s", treatment_id)
            return self._to_entry(treatment)

    def delete_treatment(self, actor: AuthenticatedUser, treatment_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            treatment_service = TreatmentService(session)
            treatment = treatment_service.get_by_id(treatment_id)
            if treatment is None:
                raise TreatmentError("Treatment record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, treatment.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_HEALTH)
            treatment_service.delete(treatment_id)
            self.logger.info("Treatment deactivated: id=%s", treatment_id)

    # ---- Validation -------------------------------------------------------

    @staticmethod
    def _validate_fields(medicine_name: str, cost: Optional[float]) -> None:
        if not medicine_name.strip():
            raise TreatmentError("Medicine name is required.")
        if cost is not None and not validate_non_negative(cost):
            raise TreatmentError("Cost cannot be negative.")

    # ---- Mapping ------------------------------------------------------------

    @staticmethod
    def _to_entry(treatment: Treatment) -> TreatmentEntry:
        return TreatmentEntry(
            id=treatment.id,
            cow_id=treatment.cow_id,
            disease_id=treatment.disease_id,
            medicine_name=treatment.medicine_name,
            dosage=treatment.dosage,
            treatment_date=treatment.treatment_date,
            administered_by=treatment.administered_by,
            cost=treatment.cost,
            notes=treatment.notes,
            recorded_by_name=treatment.recorded_by.full_name,
            is_active=treatment.is_active,
        )
