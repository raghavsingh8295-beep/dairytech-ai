"""Finance module entities: Income and Expense.

Deliberately does NOT include Feed or Medicine as expense categories.
Those costs already exist as real data — feed/medicine purchases in the
Inventory module (`StockMovement`), medicine/vaccination costs in the
Health module (`Treatment.cost`, `Vaccination.cost`) — so re-entering
them here would double-count. `FinanceSummaryService` aggregates those at
report time instead; see `controllers/finance_summary_controller.py`.
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


class IncomeCategory(str, enum.Enum):
    MILK_SALES = "milk_sales"
    CALF_SALES = "calf_sales"
    LIVESTOCK_SALES = "livestock_sales"
    MANURE_SALES = "manure_sales"
    OTHER = "other"

    @property
    def label(self) -> str:
        return {
            "milk_sales": "Milk Sales",
            "calf_sales": "Calf Sales",
            "livestock_sales": "Livestock Sales",
            "manure_sales": "Manure Sales",
            "other": "Other",
        }[self.value]


class ExpenseCategory(str, enum.Enum):
    LABOR = "labor"
    UTILITIES = "utilities"
    EQUIPMENT = "equipment"
    INSURANCE = "insurance"
    RENT_LEASE = "rent_lease"
    TAXES = "taxes"
    OTHER = "other"

    @property
    def label(self) -> str:
        return {
            "labor": "Labor",
            "utilities": "Utilities",
            "equipment": "Equipment",
            "insurance": "Insurance",
            "rent_lease": "Rent / Lease",
            "taxes": "Taxes",
            "other": "Other",
        }[self.value]


class Income(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "income_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), nullable=False)

    category: Mapped[IncomeCategory] = mapped_column(
        SAEnum(IncomeCategory, name="income_category"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    income_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    farm: Mapped[Farm] = relationship("Farm", backref="income_entries")
    recorded_by: Mapped[User] = relationship("User", backref="income_entries_logged")


class Expense(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "expense_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), nullable=False)

    category: Mapped[ExpenseCategory] = mapped_column(
        SAEnum(ExpenseCategory, name="expense_category"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    farm: Mapped[Farm] = relationship("Farm", backref="expense_entries")
    recorded_by: Mapped[User] = relationship("User", backref="expense_entries_logged")
