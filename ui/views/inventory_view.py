"""Inventory module — tabbed view for a farm: Items and Suppliers.

Farm-scoped, not cow-scoped: reached from Farm Detail, not Cow Detail,
since stock (feed, medicine, equipment) belongs to the farm as a whole.
"""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.inventory_item_controller import InventoryItemController, InventoryItemEntry
from controllers.supplier_controller import SupplierController, SupplierEntry
from ui.views.inventory_item_form_dialog import InventoryItemFormDialog
from ui.views.supplier_form_dialog import SupplierFormDialog
from utils.exceptions import AppError
from utils.permissions import Permission, has_permission


class InventoryView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        *,
        current_user: AuthenticatedUser,
        farm_id: int,
        farm_name: str,
        on_back: Callable[[], None],
        on_open_item: Callable[[int], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._item_ctl = InventoryItemController()
        self._supplier_ctl = SupplierController()
        self._current_user = current_user
        self._farm_id = farm_id
        self._on_open_item = on_open_item
        self._can_manage = has_permission(current_user.role, Permission.MANAGE_INVENTORY)

        ctk.CTkButton(self, text="← Back to Farm", command=on_back, fg_color="transparent").pack(
            anchor="w", padx=40, pady=(20, 0)
        )
        ctk.CTkLabel(
            self, text=f"Inventory — {farm_name}", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w", padx=40, pady=(8, 12))

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=40, pady=(0, 24))
        self.tabs.add("Items")
        self.tabs.add("Suppliers")

        self._build_items_tab()
        self._build_suppliers_tab()

    # ---- Items -----------------------------------------------------------

    def _build_items_tab(self) -> None:
        tab = self.tabs.tab("Items")
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(10, 6))
        if self._can_manage:
            ctk.CTkButton(header, text="+ Add Item", command=self._open_add_item).pack(side="right")

        self.item_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.item_list.pack(fill="both", expand=True)
        self._refresh_items()

    def _refresh_items(self) -> None:
        for widget in self.item_list.winfo_children():
            widget.destroy()
        items = self._item_ctl.list_for_farm(self._current_user, self._farm_id)
        if not items:
            ctk.CTkLabel(self.item_list, text="No inventory items yet.", text_color=("gray30", "gray70")).pack(
                pady=20
            )
            return
        for item in items:
            self._render_item_row(item)

    def _render_item_row(self, item: InventoryItemEntry) -> None:
        row = ctk.CTkFrame(self.item_list, corner_radius=8)
        row.pack(fill="x", pady=3)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(info, text=item.name, font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x")

        stock_color = ("#b91c1c", "#f87171") if item.is_low_stock else ("gray30", "gray70")
        stock_text = f"{item.category.label}  ·  {item.current_stock:g} {item.unit}"
        if item.is_low_stock:
            stock_text += "  ⚠ Low stock"
        ctk.CTkLabel(info, text=stock_text, anchor="w", text_color=stock_color).pack(fill="x")

        ctk.CTkButton(row, text="Open", width=80, command=lambda: self._on_open_item(item.id)).pack(
            side="right", padx=14, pady=8
        )

    def _open_add_item(self) -> None:
        InventoryItemFormDialog(
            self, current_user=self._current_user, farm_id=self._farm_id, on_saved=self._refresh_items
        )

    # ---- Suppliers ---------------------------------------------------------

    def _build_suppliers_tab(self) -> None:
        tab = self.tabs.tab("Suppliers")
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(10, 6))
        if self._can_manage:
            ctk.CTkButton(header, text="+ Add Supplier", command=self._open_add_supplier).pack(side="right")

        self.supplier_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.supplier_list.pack(fill="both", expand=True)
        self._refresh_suppliers()

    def _refresh_suppliers(self) -> None:
        for widget in self.supplier_list.winfo_children():
            widget.destroy()
        suppliers = self._supplier_ctl.list_for_farm(self._current_user, self._farm_id)
        if not suppliers:
            ctk.CTkLabel(
                self.supplier_list, text="No suppliers yet.", text_color=("gray30", "gray70")
            ).pack(pady=20)
            return
        for supplier in suppliers:
            self._render_supplier_row(supplier)

    def _render_supplier_row(self, supplier: SupplierEntry) -> None:
        row = ctk.CTkFrame(self.supplier_list, corner_radius=8)
        row.pack(fill="x", pady=3)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(info, text=supplier.name, font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x")
        contact_parts = [p for p in (supplier.contact_phone, supplier.contact_email) if p]
        if contact_parts:
            ctk.CTkLabel(info, text="  ·  ".join(contact_parts), anchor="w", text_color=("gray30", "gray70")).pack(
                fill="x"
            )

        if self._can_manage:
            ctk.CTkButton(
                row, text="Edit", width=70, command=lambda: self._open_edit_supplier(supplier)
            ).pack(side="right", padx=(4, 10), pady=8)
            ctk.CTkButton(
                row,
                text="Remove",
                width=70,
                fg_color="transparent",
                border_width=1,
                command=lambda: self._remove_supplier(supplier.id),
            ).pack(side="right", pady=8)

    def _open_add_supplier(self) -> None:
        SupplierFormDialog(
            self, current_user=self._current_user, farm_id=self._farm_id, on_saved=self._refresh_suppliers
        )

    def _open_edit_supplier(self, supplier: SupplierEntry) -> None:
        SupplierFormDialog(
            self,
            current_user=self._current_user,
            farm_id=self._farm_id,
            on_saved=self._refresh_suppliers,
            supplier=supplier,
        )

    def _remove_supplier(self, supplier_id: int) -> None:
        try:
            self._supplier_ctl.delete_supplier(self._current_user, supplier_id)
        except AppError:
            pass
        self._refresh_suppliers()
