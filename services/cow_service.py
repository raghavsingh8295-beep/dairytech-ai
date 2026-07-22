from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence

from sqlalchemy import func, select

from models.cow import Cow, HealthStatus
from services.base_service import BaseService


class CowService(BaseService[Cow]):
    model = Cow

    def list_for_farm(self, farm_id: int, *, include_inactive: bool = False) -> List[Cow]:
        stmt = select(Cow).where(Cow.farm_id == farm_id)
        if not include_inactive:
            stmt = stmt.where(Cow.is_active.is_(True))
        return list(self.session.execute(stmt).scalars().all())

    def count_for_farm(self, farm_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(Cow)
            .where(Cow.farm_id == farm_id, Cow.is_active.is_(True))
        )
        return self.session.execute(stmt).scalar_one()

    def tag_number_exists(
        self, farm_id: int, tag_number: str, *, exclude_cow_id: Optional[int] = None
    ) -> bool:
        stmt = select(Cow).where(
            Cow.farm_id == farm_id, func.lower(Cow.tag_number) == tag_number.strip().lower()
        )
        if exclude_cow_id is not None:
            stmt = stmt.where(Cow.id != exclude_cow_id)
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def rfid_exists(self, rfid_number: str, *, exclude_cow_id: Optional[int] = None) -> bool:
        stmt = select(Cow).where(func.lower(Cow.rfid_number) == rfid_number.strip().lower())
        if exclude_cow_id is not None:
            stmt = stmt.where(Cow.id != exclude_cow_id)
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def count_by_health_status(self, farm_ids: Sequence[int]) -> Dict[HealthStatus, int]:
        """For the Dashboard's Healthy/Sick Cows cards — one grouped query
        across every farm the actor can see, not a per-farm loop."""
        stmt = (
            select(Cow.health_status, func.count())
            .where(Cow.farm_id.in_(farm_ids), Cow.is_active.is_(True))
            .group_by(Cow.health_status)
        )
        return dict(self.session.execute(stmt).all())

    def count_upcoming_births(self, farm_ids: Sequence[int], *, within_days: int, as_of: date) -> int:
        """Cows due (or overdue) within the window — the Dashboard's Birth
        Alerts card. No lower bound, so an overdue delivery date still
        counts; not narrowing to "still pregnant" since expected_delivery_date
        is cleared the moment a birth is actually recorded (Module 7)."""
        horizon = as_of + timedelta(days=within_days)
        stmt = (
            select(func.count())
            .select_from(Cow)
            .where(
                Cow.farm_id.in_(farm_ids),
                Cow.is_active.is_(True),
                Cow.expected_delivery_date.is_not(None),
                Cow.expected_delivery_date <= horizon,
            )
        )
        return self.session.execute(stmt).scalar_one()
