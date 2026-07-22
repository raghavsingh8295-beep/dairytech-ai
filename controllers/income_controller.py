"""Income orchestration: farm-scoped visibility/permissions.

Unlike Health/Breeding/Inventory, *viewing* financial records also
requires `MANAGE_FINANCE`, not just farm access — income and expense
figures are more sensitive than herd data, and Employees (who can view
health/breeding/inventory) don't hold this permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_farm_or_raise
from database.session import get_db_session
from models.finance import Income, IncomeCategory
from services.farm_service import FarmService
from services.income_service import IncomeService
from utils.exceptions import AppError
from utils.permissions import Permission


class IncomeError(AppError):
    """Raised for any income-record failure the UI should surface."""


@dataclass(frozen=True)
class IncomeEntry:
    id: int
    farm_id: int
    category: IncomeCategory
    amount: float
    income_date: date
    description: Optional[str]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class IncomeController(BaseController):
    def list_for_farm(self, actor: AuthenticatedUser, farm_id: int) -> List[IncomeEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = get_farm_or_raise(farm_service, farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_FINANCE)
            records = IncomeService(session).list_for_farm(farm_id)
            return [self._to_entry(r) for r in records]

    def create_income(
        self,
        actor: AuthenticatedUser,
        *,
        farm_id: int,
        category: IncomeCategory,
        amount: float,
        income_date: date,
        description: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> IncomeEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = get_farm_or_raise(farm_service, farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_FINANCE)

            self._validate_amount(amount)
            record = IncomeService(session).create(
                farm_id=farm_id,
                category=category,
                amount=amount,
                income_date=income_date,
                description=(description.strip() or None) if description else None,
                notes=(notes.strip() or None) if notes else None,
                recorded_by_id=actor.id,
            )
            self.logger.info("Income recorded: farm_id=%s category=%s amount=%s", farm_id, category.value, amount)
            return self._to_entry(record)

    def update_income(
        self,
        actor: AuthenticatedUser,
        income_id: int,
        *,
        category: IncomeCategory,
        amount: float,
        income_date: date,
        description: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> IncomeEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            income_service = IncomeService(session)
            record = income_service.get_by_id(income_id)
            if record is None:
                raise IncomeError("Income record not found.")
            farm = get_farm_or_raise(farm_service, record.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_FINANCE)

            self._validate_amount(amount)
            income_service.update(
                income_id,
                category=category,
                amount=amount,
                income_date=income_date,
                description=(description.strip() or None) if description else None,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Income updated: id=%s", income_id)
            return self._to_entry(record)

    def delete_income(self, actor: AuthenticatedUser, income_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            income_service = IncomeService(session)
            record = income_service.get_by_id(income_id)
            if record is None:
                raise IncomeError("Income record not found.")
            farm = get_farm_or_raise(farm_service, record.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_FINANCE)
            income_service.delete(income_id)
            self.logger.info("Income deactivated: id=%s", income_id)

    @staticmethod
    def _validate_amount(amount: float) -> None:
        if amount <= 0:
            raise IncomeError("Amount must be greater than zero.")

    @staticmethod
    def _to_entry(record: Income) -> IncomeEntry:
        return IncomeEntry(
            id=record.id,
            farm_id=record.farm_id,
            category=record.category,
            amount=record.amount,
            income_date=record.income_date,
            description=record.description,
            notes=record.notes,
            recorded_by_name=record.recorded_by.full_name,
            is_active=record.is_active,
        )
