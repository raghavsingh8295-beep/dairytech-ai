from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select

from models.inventory import InventoryCategory, InventoryItem
from services.base_service import BaseService


class InventoryItemService(BaseService[InventoryItem]):
    model = InventoryItem

    def list_for_farm(
        self, farm_id: int, *, category: Optional[InventoryCategory] = None
    ) -> List[InventoryItem]:
        stmt = select(InventoryItem).where(InventoryItem.farm_id == farm_id, InventoryItem.is_active.is_(True))
        if category is not None:
            stmt = stmt.where(InventoryItem.category == category)
        stmt = stmt.order_by(InventoryItem.name.asc())
        return list(self.session.execute(stmt).scalars().all())

    def name_exists(self, farm_id: int, name: str, *, exclude_item_id: Optional[int] = None) -> bool:
        stmt = select(InventoryItem).where(
            InventoryItem.farm_id == farm_id, func.lower(InventoryItem.name) == name.strip().lower()
        )
        if exclude_item_id is not None:
            stmt = stmt.where(InventoryItem.id != exclude_item_id)
        return self.session.execute(stmt).scalar_one_or_none() is not None
