from __future__ import annotations

from typing import List

from sqlalchemy import func, select

from models.inventory import StockMovement
from services.base_service import BaseService


class StockMovementService(BaseService[StockMovement]):
    model = StockMovement

    def list_for_item(self, item_id: int) -> List[StockMovement]:
        stmt = (
            select(StockMovement)
            .where(StockMovement.item_id == item_id, StockMovement.is_active.is_(True))
            .order_by(StockMovement.movement_date.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def current_stock(self, item_id: int) -> float:
        stmt = select(func.coalesce(func.sum(StockMovement.quantity_change), 0.0)).where(
            StockMovement.item_id == item_id, StockMovement.is_active.is_(True)
        )
        return self.session.execute(stmt).scalar_one()
