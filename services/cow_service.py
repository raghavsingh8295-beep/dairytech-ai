from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select

from models.cow import Cow
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
