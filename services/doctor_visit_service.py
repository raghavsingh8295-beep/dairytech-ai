from __future__ import annotations

from datetime import date
from typing import List

from sqlalchemy import select

from models.health import DoctorVisit
from services.base_service import BaseService


class DoctorVisitService(BaseService[DoctorVisit]):
    model = DoctorVisit

    def list_for_cow(self, cow_id: int) -> List[DoctorVisit]:
        stmt = (
            select(DoctorVisit)
            .where(DoctorVisit.cow_id == cow_id, DoctorVisit.is_active.is_(True))
            .order_by(DoctorVisit.visit_date.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_upcoming_follow_ups_for_cow(self, cow_id: int, *, within_days: int, as_of: date) -> List[DoctorVisit]:
        from datetime import timedelta

        horizon = as_of + timedelta(days=within_days)
        stmt = (
            select(DoctorVisit)
            .where(
                DoctorVisit.cow_id == cow_id,
                DoctorVisit.is_active.is_(True),
                DoctorVisit.follow_up_date.is_not(None),
                DoctorVisit.follow_up_date <= horizon,
            )
            .order_by(DoctorVisit.follow_up_date.asc())
        )
        return list(self.session.execute(stmt).scalars().all())
