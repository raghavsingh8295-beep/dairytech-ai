"""Modal dialog for recording a stock movement — purchase, usage, or
adjustment, fixed at construction time rather than user-selectable, since
each entry point (a distinct button on the item detail screen) already
knows which kind of movement it means. Only fields relevant to that type
are shown: a purchase asks for supplier/unit cost, usage and adjustments
don't.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, List, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.stock_movement_controller import StockMovementController
from controllers.supplier_controller import SupplierController, SupplierEntry
from models.inventory import MovementType
from utils.exceptions import AppError
from utils.parsing import parse_optional_date, parse_optional_float

_NO_SUPPLIER = "No supplier"
FIELD_WIDTH = 340


class StockMovementFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        item_id: int,
        farm_id: int,
        movement_type: MovementType,
        on_saved: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self._controller = StockMovementController()
        self._current_user = current_user
        self._item_id = item_id
        self._movement_type = movement_type
        self._on_saved = on_saved

        self.title(f"Record {movement_type.label}")
        self.geometry("400x480")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        quantity_label = (
            "Quantity change (+ to increase, - to decrease)"
            if movement_type == MovementType.ADJUSTMENT
            else "Quantity"
        )
        self.quantity_entry = self._field(body, quantity_label)

        self.date_entry = self._field(
            body, "Date (YYYY-MM-DD)", initial=date.today().isoformat()
        )

        self.supplier_menu: Optional[ctk.CTkOptionMenu] = None
        self._suppliers: List[SupplierEntry] = []
        self.cost_entry: Optional[ctk.CTkEntry] = None
        if movement_type == MovementType.PURCHASE:
            self._suppliers = SupplierController().list_for_farm(current_user, farm_id)
            values = [_NO_SUPPLIER] + [s.name for s in self._suppliers]
            self.supplier_menu = ctk.CTkOptionMenu(body, values=values)
            self.supplier_menu.set(_NO_SUPPLIER)
            self.supplier_menu.pack(pady=5, fill="x")
            self.cost_entry = self._field(body, "Unit cost (optional)")

        self.notes_entry = ctk.CTkTextbox(body, height=70)
        self.notes_entry.pack(pady=5, fill="x")

        self.error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"), wraplength=FIELD_WIDTH)
        self.error_label.pack(pady=(8, 0))

        ctk.CTkButton(body, text="Save", command=self._submit).pack(pady=(14, 0), fill="x")

    def _field(self, parent: ctk.CTkFrame, placeholder: str, *, initial: str = "") -> ctk.CTkEntry:
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder)
        entry.pack(pady=5, fill="x")
        if initial:
            entry.insert(0, initial)
        return entry

    def _resolve_selected_supplier_id(self) -> Optional[int]:
        if self.supplier_menu is None:
            return None
        selected = self.supplier_menu.get()
        if selected == _NO_SUPPLIER:
            return None
        match = next((s for s in self._suppliers if s.name == selected), None)
        return match.id if match else None

    def _submit(self) -> None:
        try:
            movement_date = parse_optional_date(self.date_entry.get(), "Date")
            if movement_date is None:
                raise AppError("Date is required.")
            quantity_raw = parse_optional_float(self.quantity_entry.get(), "Quantity")
            if quantity_raw is None:
                raise AppError("Quantity is required.")
            notes = self.notes_entry.get("1.0", "end").strip()

            if self._movement_type == MovementType.PURCHASE:
                unit_cost = parse_optional_float(self.cost_entry.get(), "Unit cost") if self.cost_entry else None
                self._controller.record_purchase(
                    self._current_user,
                    item_id=self._item_id,
                    quantity=quantity_raw,
                    movement_date=movement_date,
                    supplier_id=self._resolve_selected_supplier_id(),
                    unit_cost=unit_cost,
                    notes=notes,
                )
            elif self._movement_type == MovementType.USAGE:
                self._controller.record_usage(
                    self._current_user,
                    item_id=self._item_id,
                    quantity=quantity_raw,
                    movement_date=movement_date,
                    notes=notes,
                )
            else:
                self._controller.record_adjustment(
                    self._current_user,
                    item_id=self._item_id,
                    quantity_change=quantity_raw,
                    movement_date=movement_date,
                    notes=notes,
                )
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
