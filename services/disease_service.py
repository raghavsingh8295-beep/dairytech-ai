from __future__ import annotations

from typing import List

from sqlalchemy import select

from models.health import Disease, DiseaseStatus
from services.base_service import BaseService


class DiseaseService(BaseService[Disease]):
    model = Disease

    def list_for_cow(self, cow_id: int) -> List[Disease]:
        stmt = (
            select(Disease)
            .where(Disease.cow_id == cow_id, Disease.is_active.is_(True))
            .order_by(Disease.diagnosed_date.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_unresolved_for_cow(self, cow_id: int) -> List[Disease]:
        stmt = select(Disease).where(
            Disease.cow_id == cow_id,
            Disease.is_active.is_(True),
            Disease.status != DiseaseStatus.RECOVERED,
        )
        return list(self.session.execute(stmt).scalars().all())
