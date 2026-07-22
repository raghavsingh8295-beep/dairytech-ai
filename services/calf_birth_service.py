from __future__ import annotations

from typing import List

from sqlalchemy import select

from models.breeding import CalfBirth
from services.base_service import BaseService


class CalfBirthService(BaseService[CalfBirth]):
    model = CalfBirth

    def list_for_mother(self, mother_cow_id: int) -> List[CalfBirth]:
        stmt = (
            select(CalfBirth)
            .where(CalfBirth.mother_cow_id == mother_cow_id, CalfBirth.is_active.is_(True))
            .order_by(CalfBirth.birth_date.desc())
        )
        return list(self.session.execute(stmt).scalars().all())
