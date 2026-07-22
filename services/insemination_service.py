from __future__ import annotations

from typing import List

from sqlalchemy import select

from models.breeding import Insemination
from services.base_service import BaseService


class InseminationService(BaseService[Insemination]):
    model = Insemination

    def list_for_cow(self, cow_id: int) -> List[Insemination]:
        stmt = (
            select(Insemination)
            .where(Insemination.cow_id == cow_id, Insemination.is_active.is_(True))
            .order_by(Insemination.insemination_date.desc())
        )
        return list(self.session.execute(stmt).scalars().all())
