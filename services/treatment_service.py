from __future__ import annotations

from typing import List

from sqlalchemy import select

from models.health import Treatment
from services.base_service import BaseService


class TreatmentService(BaseService[Treatment]):
    model = Treatment

    def list_for_cow(self, cow_id: int) -> List[Treatment]:
        stmt = (
            select(Treatment)
            .where(Treatment.cow_id == cow_id, Treatment.is_active.is_(True))
            .order_by(Treatment.treatment_date.desc())
        )
        return list(self.session.execute(stmt).scalars().all())
