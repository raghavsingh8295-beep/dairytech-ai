"""Pregnancy test orchestration: farm-scoped visibility/permissions, plus
syncing `Cow.pregnancy_status` / `expected_delivery_date` from the most
recent test — the promise made back in Module 3 for these snapshot fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_cow_or_raise, get_farm_or_raise
from database.session import get_db_session
from models.breeding import PregnancyCheck, PregnancyResult
from models.cow import PregnancyStatus
from services.cow_service import CowService
from services.farm_service import FarmService
from services.pregnancy_check_service import PregnancyCheckService
from utils.exceptions import AppError
from utils.permissions import Permission

_RESULT_TO_COW_STATUS = {
    PregnancyResult.PREGNANT: PregnancyStatus.PREGNANT,
    PregnancyResult.NOT_PREGNANT: PregnancyStatus.OPEN,
    PregnancyResult.INCONCLUSIVE: PregnancyStatus.UNKNOWN,
}


class PregnancyCheckError(AppError):
    """Raised for any pregnancy-check-record failure the UI should surface."""


@dataclass(frozen=True)
class PregnancyCheckEntry:
    id: int
    cow_id: int
    insemination_id: Optional[int]
    check_date: date
    method: Optional[str]
    result: PregnancyResult
    expected_delivery_date: Optional[date]
    performed_by: Optional[str]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class PregnancyCheckController(BaseController):
    def list_for_cow(self, actor: AuthenticatedUser, cow_id: int) -> List[PregnancyCheckEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            records = PregnancyCheckService(session).list_for_cow(cow_id)
            return [self._to_entry(r) for r in records]

    def create_check(
        self,
        actor: AuthenticatedUser,
        *,
        cow_id: int,
        check_date: date,
        result: PregnancyResult,
        insemination_id: Optional[int] = None,
        method: Optional[str] = None,
        expected_delivery_date: Optional[date] = None,
        performed_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> PregnancyCheckEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            check_service = PregnancyCheckService(session)
            cow = get_cow_or_raise(cow_service, cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_BREEDING)

            record = check_service.create(
                cow_id=cow_id,
                insemination_id=insemination_id,
                check_date=check_date,
                method=(method.strip() or None) if method else None,
                result=result,
                expected_delivery_date=expected_delivery_date if result == PregnancyResult.PREGNANT else None,
                performed_by=(performed_by.strip() or None) if performed_by else None,
                notes=(notes.strip() or None) if notes else None,
                recorded_by_id=actor.id,
            )
            self.logger.info("Pregnancy check recorded: cow_id=%s result=%s", cow_id, result.value)
            self._sync_cow_pregnancy(cow_service, check_service, cow_id, check_date, result, expected_delivery_date)
            return self._to_entry(record)

    def update_check(
        self,
        actor: AuthenticatedUser,
        check_id: int,
        *,
        check_date: date,
        result: PregnancyResult,
        insemination_id: Optional[int] = None,
        method: Optional[str] = None,
        expected_delivery_date: Optional[date] = None,
        performed_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> PregnancyCheckEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            check_service = PregnancyCheckService(session)
            record = check_service.get_by_id(check_id)
            if record is None:
                raise PregnancyCheckError("Pregnancy check record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, record.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_BREEDING)

            resolved_expected_delivery = expected_delivery_date if result == PregnancyResult.PREGNANT else None
            check_service.update(
                check_id,
                insemination_id=insemination_id,
                check_date=check_date,
                method=(method.strip() or None) if method else None,
                result=result,
                expected_delivery_date=resolved_expected_delivery,
                performed_by=(performed_by.strip() or None) if performed_by else None,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Pregnancy check updated: id=%s", check_id)
            self._sync_cow_pregnancy(
                cow_service, check_service, record.cow_id, check_date, result, resolved_expected_delivery
            )
            return self._to_entry(record)

    def delete_check(self, actor: AuthenticatedUser, check_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            check_service = PregnancyCheckService(session)
            record = check_service.get_by_id(check_id)
            if record is None:
                raise PregnancyCheckError("Pregnancy check record not found.")
            farm = get_farm_or_raise(farm_service, get_cow_or_raise(cow_service, record.cow_id).farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_BREEDING)
            check_service.delete(check_id)
            self.logger.info("Pregnancy check deactivated: id=%s", check_id)

    # ---- Cow snapshot sync --------------------------------------------------

    @staticmethod
    def _sync_cow_pregnancy(
        cow_service: CowService,
        check_service: PregnancyCheckService,
        cow_id: int,
        check_date: date,
        result: PregnancyResult,
        expected_delivery_date: Optional[date],
    ) -> None:
        """Only the most recent check drives the cow's snapshot — an older,
        backdated check being edited shouldn't override newer information."""
        latest_date = check_service.latest_check_date(cow_id)
        if latest_date is not None and check_date < latest_date:
            return
        cow_service.update(
            cow_id,
            pregnancy_status=_RESULT_TO_COW_STATUS[result],
            expected_delivery_date=expected_delivery_date,
        )

    # ---- Mapping ------------------------------------------------------------

    @staticmethod
    def _to_entry(record: PregnancyCheck) -> PregnancyCheckEntry:
        return PregnancyCheckEntry(
            id=record.id,
            cow_id=record.cow_id,
            insemination_id=record.insemination_id,
            check_date=record.check_date,
            method=record.method,
            result=record.result,
            expected_delivery_date=record.expected_delivery_date,
            performed_by=record.performed_by,
            notes=record.notes,
            recorded_by_name=record.recorded_by.full_name,
            is_active=record.is_active,
        )
