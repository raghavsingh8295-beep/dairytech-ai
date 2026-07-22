"""Inventory module entities: suppliers, items, and stock movements.

There is no stored "current stock" column anywhere — it's the sum of a
farm's `StockMovement` ledger for that item (purchases positive, usage
negative, adjustments either sign), the same "computed, not stored"
philosophy used for every other running total in this app (total milk,
cow/employee counts, ...). This also means a purchase and a manual usage
correction are the same kind of row, not two different subsystems.
"""
from __future__ import annotations

import enum
from datetime import date
from typing import Optional

from sqlalchemy import Date, Float
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.farm import Farm
from models.mixins import SoftDeleteMixin, TimestampMixin
from models.user import User


class InventoryCategory(str, enum.Enum):
    FEED = "feed"
    MEDICINE = "medicine"
    EQUIPMENT = "equipment"
    OTHER = "other"

    @property
    def label(self) -> str:
        return {"feed": "Feed", "medicine": "Medicine", "equipment": "Equipment", "other": "Other"}[self.value]


class MovementType(str, enum.Enum):
    PURCHASE = "purchase"
    USAGE = "usage"
    ADJUSTMENT = "adjustment"

    @property
    def label(self) -> str:
        return {"purchase": "Purchase", "usage": "Usage", "adjustment": "Adjustment"}[self.value]


class Supplier(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    farm: Mapped[Farm] = relationship("Farm", backref="suppliers")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Supplier id={self.id} name={self.name!r}>"


class InventoryItem(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[InventoryCategory] = mapped_column(
        SAEnum(InventoryCategory, name="inventory_category"), nullable=False
    )
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    reorder_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    farm: Mapped[Farm] = relationship("Farm", backref="inventory_items")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<InventoryItem id={self.id} name={self.name!r}>"


class StockMovement(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), nullable=False)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)

    movement_type: Mapped[MovementType] = mapped_column(
        SAEnum(MovementType, name="movement_type"), nullable=False
    )
    # Signed: positive increases stock, negative decreases it. Purchases are
    # always stored positive, usage always negative; adjustments may be
    # either — see StockMovementController for the sign-normalizing API.
    quantity_change: Mapped[float] = mapped_column(Float, nullable=False)
    unit_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    item: Mapped[InventoryItem] = relationship("InventoryItem", backref="movements")
    supplier: Mapped[Optional[Supplier]] = relationship("Supplier", backref="movements")
    recorded_by: Mapped[User] = relationship("User", backref="stock_movements_logged")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StockMovement item_id={self.item_id} type={self.movement_type.value} qty={self.quantity_change}>"
