from __future__ import annotations

from datetime import date, timedelta
from typing import List, Sequence

from sqlalchemy import func, select

from models.cow import Cow
from models.health import Vaccination
from services.base_service import BaseService


class VaccinationService(BaseService[Vaccination]):
    model = Vaccination

    def list_for_cow(self, cow_id: int) -> List[Vaccination]:
        stmt = (
            select(Vaccination)
            .where(Vaccination.cow_id == cow_id, Vaccination.is_active.is_(True))
            .order_by(Vaccination.scheduled_date.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_due_for_cow(self, cow_id: int, *, within_days: int, as_of: date) -> List[Vaccination]:
        """Pending doses (not yet given) due on/before `as_of + within_days`,
        including any already overdue."""
        horizon = as_of + timedelta(days=within_days)
        stmt = (
            select(Vaccination)
            .where(
                Vaccination.cow_id == cow_id,
                Vaccination.is_active.is_(True),
                Vaccination.date_given.is_(None),
                Vaccination.scheduled_date <= horizon,
            )
            .order_by(Vaccination.scheduled_date.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def count_due_for_farms(self, farm_ids: Sequence[int], *, within_days: int, as_of: date) -> int:
        """For the Dashboard's Upcoming Vaccinations card — one query
        across every farm the actor can see rather than looping per cow."""
        horizon = as_of + timedelta(days=within_days)
        stmt = (
            select(func.count())
            .select_from(Vaccination)
            .join(Cow, Vaccination.cow_id == Cow.id)
            .where(
                Cow.farm_id.in_(farm_ids),
                Vaccination.is_active.is_(True),
                Vaccination.date_given.is_(None),
                Vaccination.scheduled_date <= horizon,
            )
        )
        return self.session.execute(stmt).scalar_one()
