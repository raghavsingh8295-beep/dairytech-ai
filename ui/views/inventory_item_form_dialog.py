"""Modal dialog for adding or editing an inventory item's definition
(name, category, unit, reorder threshold) — not its stock level, which is
recorded separately via purchase/usage/adjustment (see
`StockMovementFormDialog`).
"""
from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.inventory_item_controller import InventoryItemController, InventoryItemEntry
from models.inventory import InventoryCategory
from utils.enum_utils import label_lookup
from utils.exceptions import AppError
from utils.parsing import parse_optional_float

FIELD_WIDTH = 340


class InventoryItemFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        farm_id: int,
        on_saved: Callable[[], None],
        item: Optional[InventoryItemEntry] = None,
    ) -> None:
        super().__init__(master)
        self._controller = InventoryItemController()
        self._current_user = current_user
        self._farm_id = farm_id
        self._on_saved = on_saved
        self._item = item

        self.title("Edit Item" if item else "Add Inventory Item")
        self.geometry("400x460")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        self.name_entry = self._field(body, "Item name", initial=item.name if item else "")

        self.category_lookup = label_lookup(InventoryCategory)
        self.category_menu = ctk.CTkOptionMenu(body, values=list(self.category_lookup))
        self.category_menu.set(item.category.label if item else InventoryCategory.FEED.label)
        self.category_menu.pack(pady=5, fill="x")

        self.unit_entry = self._field(body, "Unit (e.g. kg, liters, bags)", initial=item.unit if item else "")
        self.reorder_entry = self._field(
            body,
            "Reorder threshold (optional)",
            initial=str(item.reorder_threshold) if item and item.reorder_threshold is not None else "",
        )

        self.notes_entry = ctk.CTkTextbox(body, height=70)
        self.notes_entry.pack(pady=5, fill="x")
        if item and item.notes:
            self.notes_entry.insert("1.0", item.notes)

        self.error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"), wraplength=FIELD_WIDTH)
        self.error_label.pack(pady=(8, 0))

        ctk.CTkButton(body, text="Save", command=self._submit).pack(pady=(14, 0), fill="x")

    def _field(self, parent: ctk.CTkFrame, placeholder: str, *, initial: str = "") -> ctk.CTkEntry:
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder)
        entry.pack(pady=5, fill="x")
        if initial:
            entry.insert(0, initial)
        return entry

    def _submit(self) -> None:
        try:
            reorder_threshold = parse_optional_float(self.reorder_entry.get(), "Reorder threshold")
            category = self.category_lookup[self.category_menu.get()]
            notes = self.notes_entry.get("1.0", "end").strip()

            kwargs = dict(
                name=self.name_entry.get(),
                category=category,
                unit=self.unit_entry.get(),
                reorder_threshold=reorder_threshold,
                notes=notes,
            )
            if self._item is None:
                self._controller.create_item(self._current_user, farm_id=self._farm_id, **kwargs)
            else:
                self._controller.update_item(self._current_user, self._item.id, **kwargs)
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
