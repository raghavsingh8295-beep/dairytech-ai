"""Monthly Summary orchestration: combines manually-entered Income/Expense
with aggregated Feed/Medicine costs pulled from Inventory and Health into
one Profit figure — without ever double-counting a cost recorded in two
places, since Feed/Medicine never appear in the manual Expense table at
all (see `models/finance.py`).
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_farm_or_raise
from database.session import get_db_session
from models.finance import IncomeCategory
from services.expense_service import ExpenseService
from services.farm_service import FarmService
from services.finance_summary_service import FinanceSummaryService
from services.income_service import IncomeService
from utils.permissions import Permission


@dataclass(frozen=True)
class MonthlySummary:
    farm_id: int
    year: int
    month: int
    milk_sales_income: float
    other_income: float
    total_income: float
    feed_cost: float
    medicine_cost: float
    other_expenses: float
    total_expenses: float

    @property
    def profit(self) -> float:
        return self.total_income - self.total_expenses


class FinanceSummaryController(BaseController):
    def get_monthly_summary(self, actor: AuthenticatedUser, farm_id: int, *, year: int, month: int) -> MonthlySummary:
        start_date, end_date = self._month_range(year, month)
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = get_farm_or_raise(farm_service, farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_FINANCE)

            income_service = IncomeService(session)
            expense_service = ExpenseService(session)
            aggregation_service = FinanceSummaryService(session)

            milk_sales_income = income_service.sum_for_period_by_category(
                farm_id, IncomeCategory.MILK_SALES, start_date, end_date
            )
            total_income = income_service.sum_for_period(farm_id, start_date, end_date)
            other_income = total_income - milk_sales_income

            feed_cost = aggregation_service.feed_cost_for_period(farm_id, start_date, end_date)
            medicine_cost = aggregation_service.medicine_cost_for_period(farm_id, start_date, end_date)
            other_expenses = expense_service.sum_for_period(farm_id, start_date, end_date)
            total_expenses = feed_cost + medicine_cost + other_expenses

            return MonthlySummary(
                farm_id=farm_id,
                year=year,
                month=month,
                milk_sales_income=milk_sales_income,
                other_income=other_income,
                total_income=total_income,
                feed_cost=feed_cost,
                medicine_cost=medicine_cost,
                other_expenses=other_expenses,
                total_expenses=total_expenses,
            )

    @staticmethod
    def _month_range(year: int, month: int) -> tuple[date, date]:
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
