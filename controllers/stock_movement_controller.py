"""Stock movement orchestration: farm-scoped visibility/permissions.

Exposes three narrow, intention-revealing methods (`record_purchase`,
`record_usage`, `record_adjustment`) instead of one generic "create
movement with a signed quantity" call — a farmer thinks "I bought 50kg"
or "I used 50kg", not "quantity_change = ±50". Each method normalizes the
sign before writing the row, so `StockMovement.quantity_change` in the
database is always unambiguous.

No validation blocks a usage/adjustment from taking stock negative — that
can legitimately happen when data entry lags behind reality (usage logged
before the matching purchase), and treating it as a hard error would
block a normal workflow. It's a number the UI can flag, not a rule to
enforce.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_farm_or_raise
from database.session import get_db_session
from models.inventory import MovementType, StockMovement
from services.farm_service import FarmService
from services.inventory_item_service import InventoryItemService
from services.stock_movement_service import StockMovementService
from utils.exceptions import AppError
from utils.permissions import Permission


class StockMovementError(AppError):
    """Raised for any stock-movement failure the UI should surface."""


@dataclass(frozen=True)
class StockMovementEntry:
    id: int
    item_id: int
    supplier_id: Optional[int]
    movement_type: MovementType
    quantity_change: float
    unit_cost: Optional[float]
    total_cost: Optional[float]
    movement_date: date
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class StockMovementController(BaseController):
    def list_for_item(self, actor: AuthenticatedUser, item_id: int) -> List[StockMovementEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            item = self._require_item(InventoryItemService(session), item_id)
            farm = get_farm_or_raise(farm_service, item.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            records = StockMovementService(session).list_for_item(item_id)
            return [self._to_entry(r) for r in records]

    def record_purchase(
        self,
        actor: AuthenticatedUser,
        *,
        item_id: int,
        quantity: float,
        movement_date: date,
        supplier_id: Optional[int] = None,
        unit_cost: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> StockMovementEntry:
        self._validate_quantity(quantity)
        self._validate_cost(unit_cost)
        return self._record(
            actor,
            item_id=item_id,
            movement_type=MovementType.PURCHASE,
            quantity_change=abs(quantity),
            movement_date=movement_date,
            supplier_id=supplier_id,
            unit_cost=unit_cost,
            notes=notes,
        )

    def record_usage(
        self,
        actor: AuthenticatedUser,
        *,
        item_id: int,
        quantity: float,
        movement_date: date,
        notes: Optional[str] = None,
    ) -> StockMovementEntry:
        self._validate_quantity(quantity)
        return self._record(
            actor,
            item_id=item_id,
            movement_type=MovementType.USAGE,
            quantity_change=-abs(quantity),
            movement_date=movement_date,
            supplier_id=None,
            unit_cost=None,
            notes=notes,
        )

    def record_adjustment(
        self,
        actor: AuthenticatedUser,
        *,
        item_id: int,
        quantity_change: float,
        movement_date: date,
        notes: Optional[str] = None,
    ) -> StockMovementEntry:
        if quantity_change == 0:
            raise StockMovementError("Adjustment quantity cannot be zero.")
        return self._record(
            actor,
            item_id=item_id,
            movement_type=MovementType.ADJUSTMENT,
            quantity_change=quantity_change,
            movement_date=movement_date,
            supplier_id=None,
            unit_cost=None,
            notes=notes,
        )

    def delete_movement(self, actor: AuthenticatedUser, movement_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            movement_service = StockMovementService(session)
            movement = movement_service.get_by_id(movement_id)
            if movement is None:
                raise StockMovementError("Stock movement not found.")
            item = self._require_item(InventoryItemService(session), movement.item_id)
            farm = get_farm_or_raise(farm_service, item.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_INVENTORY)
            movement_service.delete(movement_id)
            self.logger.info("Stock movement deactivated: id=%s", movement_id)

    # ---- Shared write path ---------------------------------------------------

    def _record(
        self,
        actor: AuthenticatedUser,
        *,
        item_id: int,
        movement_type: MovementType,
        quantity_change: float,
        movement_date: date,
        supplier_id: Optional[int],
        unit_cost: Optional[float],
        notes: Optional[str],
    ) -> StockMovementEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            item = self._require_item(InventoryItemService(session), item_id)
            farm = get_farm_or_raise(farm_service, item.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_INVENTORY)

            movement = StockMovementService(session).create(
                item_id=item_id,
                supplier_id=supplier_id,
                movement_type=movement_type,
                quantity_change=quantity_change,
                unit_cost=unit_cost,
                movement_date=movement_date,
                notes=(notes.strip() or None) if notes else None,
                recorded_by_id=actor.id,
            )
            self.logger.info(
                "Stock movement recorded: item_id=%s type=%s qty=%s",
                item_id,
                movement_type.value,
                quantity_change,
            )
            return self._to_entry(movement)

    # ---- Validation -------------------------------------------------------

    @staticmethod
    def _validate_quantity(quantity: float) -> None:
        if quantity <= 0:
            raise StockMovementError("Quantity must be greater than zero.")

    @staticmethod
    def _validate_cost(unit_cost: Optional[float]) -> None:
        if unit_cost is not None and unit_cost < 0:
            raise StockMovementError("Unit cost cannot be negative.")

    @staticmethod
    def _require_item(item_service: InventoryItemService, item_id: int):
        item = item_service.get_by_id(item_id)
        if item is None:
            raise StockMovementError("Inventory item not found.")
        return item

    # ---- Mapping ------------------------------------------------------------

    @staticmethod
    def _to_entry(movement: StockMovement) -> StockMovementEntry:
        total_cost = (
            movement.quantity_change * movement.unit_cost
            if movement.unit_cost is not None
            else None
        )
        return StockMovementEntry(
            id=movement.id,
            item_id=movement.item_id,
            supplier_id=movement.supplier_id,
            movement_type=movement.movement_type,
            quantity_change=movement.quantity_change,
            unit_cost=movement.unit_cost,
            total_cost=total_cost,
            movement_date=movement.movement_date,
            notes=movement.notes,
            recorded_by_name=movement.recorded_by.full_name,
            is_active=movement.is_active,
        )
