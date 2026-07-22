"""Cross-module cost aggregation for the Finance module's Monthly Summary.

Not a `BaseService[Model]` — it doesn't own an entity, it reads other
modules' tables (Inventory's purchase ledger, Health's treatment and
vaccination costs) scoped to a farm and date range. This is where "Feed
Cost" and "Medicine Cost" actually come from, rather than requiring a
farmer to re-enter them as Finance expenses (see `models/finance.py`).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.cow import Cow
from models.health import Treatment, Vaccination
from models.inventory import InventoryCategory, InventoryItem, MovementType, StockMovement


class FinanceSummaryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def feed_cost_for_period(self, farm_id: int, start_date: date, end_date: date) -> float:
        """Sum of Feed-category inventory purchases in the period. A
        purchase with no unit cost recorded contributes nothing — there's
        no cost to attribute."""
        stmt = (
            select(func.coalesce(func.sum(StockMovement.quantity_change * StockMovement.unit_cost), 0.0))
            .join(InventoryItem, StockMovement.item_id == InventoryItem.id)
            .where(
                InventoryItem.farm_id == farm_id,
                InventoryItem.category == InventoryCategory.FEED,
                StockMovement.movement_type == MovementType.PURCHASE,
                StockMovement.unit_cost.is_not(None),
                StockMovement.is_active.is_(True),
                StockMovement.movement_date >= start_date,
                StockMovement.movement_date <= end_date,
            )
        )
        return self.session.execute(stmt).scalar_one()

    def medicine_cost_for_period(self, farm_id: int, start_date: date, end_date: date) -> float:
        """Sum of Treatment + given-Vaccination costs in the period —
        actual medicine administered, not stock purchased (which may sit
        unused for a while after buying it)."""
        treatment_stmt = (
            select(func.coalesce(func.sum(Treatment.cost), 0.0))
            .join(Cow, Treatment.cow_id == Cow.id)
            .where(
                Cow.farm_id == farm_id,
                Treatment.is_active.is_(True),
                Treatment.treatment_date >= start_date,
                Treatment.treatment_date <= end_date,
            )
        )
        vaccination_stmt = (
            select(func.coalesce(func.sum(Vaccination.cost), 0.0))
            .join(Cow, Vaccination.cow_id == Cow.id)
            .where(
                Cow.farm_id == farm_id,
                Vaccination.is_active.is_(True),
                Vaccination.date_given.is_not(None),
                Vaccination.date_given >= start_date,
                Vaccination.date_given <= end_date,
            )
        )
        treatment_total = self.session.execute(treatment_stmt).scalar_one()
        vaccination_total = self.session.execute(vaccination_stmt).scalar_one()
        return treatment_total + vaccination_total
