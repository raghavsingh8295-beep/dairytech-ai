from __future__ import annotations

from typing import List

from sqlalchemy import select

from models.inventory import Supplier
from services.base_service import BaseService


class SupplierService(BaseService[Supplier]):
    model = Supplier

    def list_for_farm(self, farm_id: int) -> List[Supplier]:
        stmt = (
            select(Supplier)
            .where(Supplier.farm_id == farm_id, Supplier.is_active.is_(True))
            .order_by(Supplier.name.asc())
        )
        return list(self.session.execute(stmt).scalars().all())
