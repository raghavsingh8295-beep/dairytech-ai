"""Inventory item orchestration: farm-scoped visibility/permissions, plus
computing each item's current stock from its movement ledger.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_farm_or_raise
from database.session import get_db_session
from models.inventory import InventoryCategory, InventoryItem
from services.farm_service import FarmService
from services.inventory_item_service import InventoryItemService
from services.stock_movement_service import StockMovementService
from utils.exceptions import AppError
from utils.permissions import Permission


class InventoryItemError(AppError):
    """Raised for any inventory-item failure the UI should surface."""


@dataclass(frozen=True)
class InventoryItemEntry:
    id: int
    farm_id: int
    name: str
    category: InventoryCategory
    unit: str
    reorder_threshold: Optional[float]
    current_stock: float
    notes: Optional[str]
    is_active: bool

    @property
    def is_low_stock(self) -> bool:
        return self.reorder_threshold is not None and self.current_stock <= self.reorder_threshold


class InventoryItemController(BaseController):
    def list_for_farm(
        self, actor: AuthenticatedUser, farm_id: int, *, category: Optional[InventoryCategory] = None
    ) -> List[InventoryItemEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = get_farm_or_raise(farm_service, farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            movement_service = StockMovementService(session)
            items = InventoryItemService(session).list_for_farm(farm_id, category=category)
            return [self._to_entry(item, movement_service) for item in items]

    def get_item(self, actor: AuthenticatedUser, item_id: int) -> InventoryItemEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            item_service = InventoryItemService(session)
            item = item_service.get_by_id(item_id)
            if item is None:
                raise InventoryItemError("Inventory item not found.")
            farm = get_farm_or_raise(farm_service, item.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            return self._to_entry(item, StockMovementService(session))

    def create_item(
        self,
        actor: AuthenticatedUser,
        *,
        farm_id: int,
        name: str,
        category: InventoryCategory,
        unit: str,
        reorder_threshold: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> InventoryItemEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            item_service = InventoryItemService(session)
            farm = get_farm_or_raise(farm_service, farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_INVENTORY)

            self._validate_fields(name, unit, reorder_threshold)
            if item_service.name_exists(farm_id, name):
                raise InventoryItemError(f"An item named '{name}' already exists on this farm.")

            item = item_service.create(
                farm_id=farm_id,
                name=name.strip(),
                category=category,
                unit=unit.strip(),
                reorder_threshold=reorder_threshold,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Inventory item created: farm_id=%s name=%s", farm_id, item.name)
            return self._to_entry(item, StockMovementService(session))

    def update_item(
        self,
        actor: AuthenticatedUser,
        item_id: int,
        *,
        name: str,
        category: InventoryCategory,
        unit: str,
        reorder_threshold: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> InventoryItemEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            item_service = InventoryItemService(session)
            item = item_service.get_by_id(item_id)
            if item is None:
                raise InventoryItemError("Inventory item not found.")
            farm = get_farm_or_raise(farm_service, item.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_INVENTORY)

            self._validate_fields(name, unit, reorder_threshold)
            if item_service.name_exists(item.farm_id, name, exclude_item_id=item_id):
                raise InventoryItemError(f"An item named '{name}' already exists on this farm.")

            item_service.update(
                item_id,
                name=name.strip(),
                category=category,
                unit=unit.strip(),
                reorder_threshold=reorder_threshold,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Inventory item updated: id=%s", item_id)
            return self._to_entry(item, StockMovementService(session))

    def delete_item(self, actor: AuthenticatedUser, item_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            item_service = InventoryItemService(session)
            item = item_service.get_by_id(item_id)
            if item is None:
                raise InventoryItemError("Inventory item not found.")
            farm = get_farm_or_raise(farm_service, item.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_INVENTORY)
            item_service.delete(item_id)
            self.logger.info("Inventory item deactivated: id=%s", item_id)

    @staticmethod
    def _validate_fields(name: str, unit: str, reorder_threshold: Optional[float]) -> None:
        if not name.strip():
            raise InventoryItemError("Item name is required.")
        if not unit.strip():
            raise InventoryItemError("Unit is required (e.g. kg, liters, bags, units).")
        if reorder_threshold is not None and reorder_threshold < 0:
            raise InventoryItemError("Reorder threshold cannot be negative.")

    @staticmethod
    def _to_entry(item: InventoryItem, movement_service: StockMovementService) -> InventoryItemEntry:
        return InventoryItemEntry(
            id=item.id,
            farm_id=item.farm_id,
            name=item.name,
            category=item.category,
            unit=item.unit,
            reorder_threshold=item.reorder_threshold,
            current_stock=movement_service.current_stock(item.id),
            notes=item.notes,
            is_active=item.is_active,
        )
