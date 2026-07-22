"""Inventory item detail — current stock, movement ledger, and the three
recording actions (Purchase, Usage, Adjustment)."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.inventory_item_controller import InventoryItemController
from controllers.stock_movement_controller import StockMovementController, StockMovementEntry
from models.inventory import MovementType
from ui.views.inventory_item_form_dialog import InventoryItemFormDialog
from ui.views.stock_movement_form_dialog import StockMovementFormDialog
from utils.exceptions import AppError
from utils.permissions import Permission, has_permission

MOVEMENT_COLORS = {
    "purchase": ("#1a7f37", "#4ade80"),
    "usage": ("#b91c1c", "#f87171"),
    "adjustment": ("#2563eb", "#60a5fa"),
}


class InventoryItemDetailView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        *,
        current_user: AuthenticatedUser,
        item_id: int,
        farm_id: int,
        on_back: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._item_ctl = InventoryItemController()
        self._movement_ctl = StockMovementController()
        self._current_user = current_user
        self._item_id = item_id
        self._farm_id = farm_id
        self._on_back = on_back
        self._can_manage = has_permission(current_user.role, Permission.MANAGE_INVENTORY)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=40, pady=24)

        self.refresh()

    def refresh(self) -> None:
        for widget in self.scroll.winfo_children():
            widget.destroy()

        try:
            item = self._item_ctl.get_item(self._current_user, self._item_id)
        except AppError as exc:
            ctk.CTkLabel(self.scroll, text=str(exc), text_color=("#b91c1c", "#f87171")).pack(pady=40)
            ctk.CTkButton(self.scroll, text="← Back", command=self._on_back).pack()
            return

        ctk.CTkButton(self.scroll, text="← Back to Inventory", command=self._on_back, fg_color="transparent").pack(
            anchor="w", pady=(0, 12)
        )

        header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        header.pack(fill="x")
        info = ctk.CTkFrame(header, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(info, text=item.name, font=ctk.CTkFont(size=24, weight="bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(info, text=item.category.label, anchor="w", text_color=("gray30", "gray70")).pack(fill="x")

        stock_color = ("#b91c1c", "#f87171") if item.is_low_stock else ("gray10", "gray90")
        stock_text = f"{item.current_stock:g} {item.unit} in stock"
        if item.is_low_stock:
            stock_text += f"  ⚠ at or below reorder threshold ({item.reorder_threshold:g})"
        ctk.CTkLabel(info, text=stock_text, anchor="w", text_color=stock_color, font=ctk.CTkFont(weight="bold")).pack(
            fill="x", pady=(4, 0)
        )

        if self._can_manage:
            ctk.CTkButton(header, text="Edit Item", width=100, command=self._open_edit_item).pack(side="right")

        if self._can_manage:
            actions = ctk.CTkFrame(self.scroll, fg_color="transparent")
            actions.pack(fill="x", pady=(16, 0))
            ctk.CTkButton(
                actions, text="+ Record Purchase", command=lambda: self._open_movement(MovementType.PURCHASE)
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                actions, text="− Record Usage", command=lambda: self._open_movement(MovementType.USAGE)
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                actions, text="Adjust Stock", command=lambda: self._open_movement(MovementType.ADJUSTMENT)
            ).pack(side="left")

        self._render_movements_section()

    def _render_movements_section(self) -> None:
        ctk.CTkLabel(self.scroll, text="Movement History", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", pady=(24, 8)
        )

        movements = self._movement_ctl.list_for_item(self._current_user, self._item_id)
        if not movements:
            ctk.CTkLabel(self.scroll, text="No movements recorded yet.", text_color=("gray30", "gray70")).pack(
                pady=20
            )
            return

        for movement in movements:
            self._render_movement_row(movement)

    def _render_movement_row(self, movement: StockMovementEntry) -> None:
        row = ctk.CTkFrame(self.scroll, corner_radius=8)
        row.pack(fill="x", pady=3)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)

        color = MOVEMENT_COLORS.get(movement.movement_type.value, ("gray30", "gray70"))
        sign = "+" if movement.quantity_change > 0 else ""
        ctk.CTkLabel(
            info,
            text=f"{movement.movement_type.label}: {sign}{movement.quantity_change:g}",
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
            text_color=color,
        ).pack(fill="x")

        detail = movement.movement_date.isoformat()
        if movement.total_cost is not None:
            detail += f"  ·  Cost: {movement.total_cost:g}"
        ctk.CTkLabel(info, text=detail, anchor="w", text_color=("gray30", "gray70")).pack(fill="x")

        if self._can_manage:
            ctk.CTkButton(
                row,
                text="Remove",
                width=80,
                fg_color="transparent",
                border_width=1,
                command=lambda: self._remove_movement(movement.id),
            ).pack(side="right", padx=10, pady=8)

    def _open_edit_item(self) -> None:
        item = self._item_ctl.get_item(self._current_user, self._item_id)
        InventoryItemFormDialog(
            self, current_user=self._current_user, farm_id=self._farm_id, on_saved=self.refresh, item=item
        )

    def _open_movement(self, movement_type: MovementType) -> None:
        StockMovementFormDialog(
            self,
            current_user=self._current_user,
            item_id=self._item_id,
            farm_id=self._farm_id,
            movement_type=movement_type,
            on_saved=self.refresh,
        )

    def _remove_movement(self, movement_id: int) -> None:
        try:
            self._movement_ctl.delete_movement(self._current_user, movement_id)
        except AppError:
            pass
        self.refresh()
