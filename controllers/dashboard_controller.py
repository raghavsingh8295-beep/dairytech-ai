"""Dashboard orchestration: KPI cards aggregated across every farm the
actor can see, reusing the exact same role-based visibility scoping
`FarmController.list_farms` established (Admin: all, Farm Owner: owned,
Employee: assigned) rather than a separate rule.

Cow/milk/vaccination aggregation runs as single grouped SQL queries
across all visible farms (see the new methods on `CowService`,
`DailyRecordService`, `VaccinationService`) instead of looping per farm
or per cow — farm counts are small, but cow and record counts are not.
Finance is the one exception: it loops `FinanceSummaryController` per
farm and sums the results, since farm counts really are small enough
that reusing Module 9's tested per-farm logic beats duplicating its
aggregation SQL for a multi-farm case that will rarely exceed a handful
of farms.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.finance_summary_controller import FinanceSummaryController
from database.session import get_db_session
from models.cow import HealthStatus
from models.user import UserRole
from services.cow_service import CowService
from services.daily_record_service import DailyRecordService
from services.farm_service import FarmService
from services.vaccination_service import VaccinationService
from utils.permissions import Permission, has_permission

_REMINDER_WINDOW_DAYS = 14


@dataclass(frozen=True)
class DashboardSummary:
    total_farms: int
    total_cows: int
    healthy_cows: int
    sick_cows: int
    milk_today_liters: float
    upcoming_vaccinations: int
    birth_alerts: int
    revenue: Optional[float]
    expenses: Optional[float]
    profit: Optional[float]


class DashboardController(BaseController):
    def get_dashboard(self, actor: AuthenticatedUser) -> DashboardSummary:
        with get_db_session() as session:
            farm_ids = self._visible_farm_ids(FarmService(session), actor)
            total_farms = len(farm_ids)

            if not farm_ids:
                health_counts = {}
                milk_today = 0.0
                birth_alerts = 0
                upcoming_vaccinations = 0
            else:
                health_counts = CowService(session).count_by_health_status(farm_ids)
                milk_today = DailyRecordService(session).sum_milk_for_farms_on_date(farm_ids, date.today())
                birth_alerts = CowService(session).count_upcoming_births(
                    farm_ids, within_days=_REMINDER_WINDOW_DAYS, as_of=date.today()
                )
                upcoming_vaccinations = VaccinationService(session).count_due_for_farms(
                    farm_ids, within_days=_REMINDER_WINDOW_DAYS, as_of=date.today()
                )

            total_cows = sum(health_counts.values())
            healthy_cows = health_counts.get(HealthStatus.HEALTHY, 0)
            sick_cows = total_cows - healthy_cows

        revenue = expenses = profit = None
        if farm_ids and has_permission(actor.role, Permission.MANAGE_FINANCE):
            revenue, expenses, profit = self._aggregate_finance(actor, farm_ids)

        return DashboardSummary(
            total_farms=total_farms,
            total_cows=total_cows,
            healthy_cows=healthy_cows,
            sick_cows=sick_cows,
            milk_today_liters=milk_today,
            upcoming_vaccinations=upcoming_vaccinations,
            birth_alerts=birth_alerts,
            revenue=revenue,
            expenses=expenses,
            profit=profit,
        )

    @staticmethod
    def _visible_farm_ids(farm_service: FarmService, actor: AuthenticatedUser) -> list[int]:
        if actor.role == UserRole.ADMIN:
            farms = farm_service.get_all()
        elif actor.role == UserRole.FARM_OWNER:
            farms = farm_service.list_owned_by(actor.id)
        else:
            farms = farm_service.list_for_employee(actor.id)
        return [f.id for f in farms]

    @staticmethod
    def _aggregate_finance(actor: AuthenticatedUser, farm_ids: list[int]) -> tuple[float, float, float]:
        today = date.today()
        summary_ctl = FinanceSummaryController()
        revenue = expenses = 0.0
        for farm_id in farm_ids:
            summary = summary_ctl.get_monthly_summary(actor, farm_id, year=today.year, month=today.month)
            revenue += summary.total_income
            expenses += summary.total_expenses
        return revenue, expenses, revenue - expenses
