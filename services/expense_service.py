from __future__ import annotations

from datetime import date
from typing import List

from sqlalchemy import func, select

from models.finance import Expense
from services.base_service import BaseService


class ExpenseService(BaseService[Expense]):
    model = Expense

    def list_for_farm(self, farm_id: int) -> List[Expense]:
        stmt = (
            select(Expense)
            .where(Expense.farm_id == farm_id, Expense.is_active.is_(True))
            .order_by(Expense.expense_date.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def sum_for_period(self, farm_id: int, start_date: date, end_date: date) -> float:
        stmt = select(func.coalesce(func.sum(Expense.amount), 0.0)).where(
            Expense.farm_id == farm_id,
            Expense.is_active.is_(True),
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date,
        )
        return self.session.execute(stmt).scalar_one()
