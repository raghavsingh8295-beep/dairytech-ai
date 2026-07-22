"""Expense orchestration: farm-scoped visibility/permissions (same
MANAGE_FINANCE-for-viewing rule as IncomeController)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_farm_or_raise
from database.session import get_db_session
from models.finance import Expense, ExpenseCategory
from services.expense_service import ExpenseService
from services.farm_service import FarmService
from utils.exceptions import AppError
from utils.permissions import Permission


class ExpenseError(AppError):
    """Raised for any expense-record failure the UI should surface."""


@dataclass(frozen=True)
class ExpenseEntry:
    id: int
    farm_id: int
    category: ExpenseCategory
    amount: float
    expense_date: date
    description: Optional[str]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class ExpenseController(BaseController):
    def list_for_farm(self, actor: AuthenticatedUser, farm_id: int) -> List[ExpenseEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = get_farm_or_raise(farm_service, farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_FINANCE)
            records = ExpenseService(session).list_for_farm(farm_id)
            return [self._to_entry(r) for r in records]

    def create_expense(
        self,
        actor: AuthenticatedUser,
        *,
        farm_id: int,
        category: ExpenseCategory,
        amount: float,
        expense_date: date,
        description: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> ExpenseEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = get_farm_or_raise(farm_service, farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_FINANCE)

            self._validate_amount(amount)
            record = ExpenseService(session).create(
                farm_id=farm_id,
                category=category,
                amount=amount,
                expense_date=expense_date,
                description=(description.strip() or None) if description else None,
                notes=(notes.strip() or None) if notes else None,
                recorded_by_id=actor.id,
            )
            self.logger.info(
                "Expense recorded: farm_id=%s category=%s amount=%s", farm_id, category.value, amount
            )
            return self._to_entry(record)

    def update_expense(
        self,
        actor: AuthenticatedUser,
        expense_id: int,
        *,
        category: ExpenseCategory,
        amount: float,
        expense_date: date,
        description: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> ExpenseEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            expense_service = ExpenseService(session)
            record = expense_service.get_by_id(expense_id)
            if record is None:
                raise ExpenseError("Expense record not found.")
            farm = get_farm_or_raise(farm_service, record.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_FINANCE)

            self._validate_amount(amount)
            expense_service.update(
                expense_id,
                category=category,
                amount=amount,
                expense_date=expense_date,
                description=(description.strip() or None) if description else None,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Expense updated: id=%s", expense_id)
            return self._to_entry(record)

    def delete_expense(self, actor: AuthenticatedUser, expense_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            expense_service = ExpenseService(session)
            record = expense_service.get_by_id(expense_id)
            if record is None:
                raise ExpenseError("Expense record not found.")
            farm = get_farm_or_raise(farm_service, record.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_FINANCE)
            expense_service.delete(expense_id)
            self.logger.info("Expense deactivated: id=%s", expense_id)

    @staticmethod
    def _validate_amount(amount: float) -> None:
        if amount <= 0:
            raise ExpenseError("Amount must be greater than zero.")

    @staticmethod
    def _to_entry(record: Expense) -> ExpenseEntry:
        return ExpenseEntry(
            id=record.id,
            farm_id=record.farm_id,
            category=record.category,
            amount=record.amount,
            expense_date=record.expense_date,
            description=record.description,
            notes=record.notes,
            recorded_by_name=record.recorded_by.full_name,
            is_active=record.is_active,
        )
