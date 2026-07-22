from __future__ import annotations

from typing import List

from sqlalchemy import select

from models.breeding import HeatCycle
from services.base_service import BaseService


class HeatCycleService(BaseService[HeatCycle]):
    model = HeatCycle

    def list_for_cow(self, cow_id: int) -> List[HeatCycle]:
        stmt = (
            select(HeatCycle)
            .where(HeatCycle.cow_id == cow_id, HeatCycle.is_active.is_(True))
            .order_by(HeatCycle.heat_date.desc())
        )
        return list(self.session.execute(stmt).scalars().all())
