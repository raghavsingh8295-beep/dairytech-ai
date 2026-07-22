from __future__ import annotations

from datetime import date
from typing import List

from sqlalchemy import func, select

from models.finance import Income
from services.base_service import BaseService


class IncomeService(BaseService[Income]):
    model = Income

    def list_for_farm(self, farm_id: int) -> List[Income]:
        stmt = (
            select(Income)
            .where(Income.farm_id == farm_id, Income.is_active.is_(True))
            .order_by(Income.income_date.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def sum_for_period(self, farm_id: int, start_date: date, end_date: date) -> float:
        stmt = select(func.coalesce(func.sum(Income.amount), 0.0)).where(
            Income.farm_id == farm_id,
            Income.is_active.is_(True),
            Income.income_date >= start_date,
            Income.income_date <= end_date,
        )
        return self.session.execute(stmt).scalar_one()

    def sum_for_period_by_category(self, farm_id: int, category, start_date: date, end_date: date) -> float:
        stmt = select(func.coalesce(func.sum(Income.amount), 0.0)).where(
            Income.farm_id == farm_id,
            Income.category == category,
            Income.is_active.is_(True),
            Income.income_date >= start_date,
            Income.income_date <= end_date,
        )
        return self.session.execute(stmt).scalar_one()
