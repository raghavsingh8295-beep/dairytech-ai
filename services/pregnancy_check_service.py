from __future__ import annotations

from datetime import date
from typing import List, Optional

from sqlalchemy import func, select

from models.breeding import PregnancyCheck
from services.base_service import BaseService


class PregnancyCheckService(BaseService[PregnancyCheck]):
    model = PregnancyCheck

    def list_for_cow(self, cow_id: int) -> List[PregnancyCheck]:
        stmt = (
            select(PregnancyCheck)
            .where(PregnancyCheck.cow_id == cow_id, PregnancyCheck.is_active.is_(True))
            .order_by(PregnancyCheck.check_date.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def latest_check_date(self, cow_id: int) -> Optional[date]:
        stmt = select(func.max(PregnancyCheck.check_date)).where(
            PregnancyCheck.cow_id == cow_id, PregnancyCheck.is_active.is_(True)
        )
        return self.session.execute(stmt).scalar_one_or_none()
