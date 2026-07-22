from __future__ import annotations

from datetime import date
from typing import List

from sqlalchemy import select

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
        from datetime import timedelta

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
