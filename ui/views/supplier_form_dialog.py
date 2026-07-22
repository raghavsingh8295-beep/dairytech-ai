"""Modal dialog for adding or editing a supplier."""
from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.supplier_controller import SupplierController, SupplierEntry
from utils.exceptions import AppError

FIELD_WIDTH = 340


class SupplierFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        farm_id: int,
        on_saved: Callable[[], None],
        supplier: Optional[SupplierEntry] = None,
    ) -> None:
        super().__init__(master)
        self._controller = SupplierController()
        self._current_user = current_user
        self._farm_id = farm_id
        self._on_saved = on_saved
        self._supplier = supplier

        self.title("Edit Supplier" if supplier else "Add Supplier")
        self.geometry("400x480")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        self.name_entry = self._field(body, "Supplier name", initial=supplier.name if supplier else "")
        self.phone_entry = self._field(body, "Phone", initial=supplier.contact_phone if supplier else "")
        self.email_entry = self._field(body, "Email", initial=supplier.contact_email if supplier else "")
        self.address_entry = self._field(body, "Address", initial=supplier.address if supplier else "")

        self.notes_entry = ctk.CTkTextbox(body, height=70)
        self.notes_entry.pack(pady=5, fill="x")
        if supplier and supplier.notes:
            self.notes_entry.insert("1.0", supplier.notes)

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
            kwargs = dict(
                name=self.name_entry.get(),
                contact_phone=self.phone_entry.get(),
                contact_email=self.email_entry.get(),
                address=self.address_entry.get(),
                notes=self.notes_entry.get("1.0", "end").strip(),
            )
            if self._supplier is None:
                self._controller.create_supplier(self._current_user, farm_id=self._farm_id, **kwargs)
            else:
                self._controller.update_supplier(self._current_user, self._supplier.id, **kwargs)
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
