"""Modal dialog for creating or editing a farm. Shared by the list "Add
Farm" button and the detail view's "Edit" button.
"""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import Callable, List, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.farm_controller import FarmController, FarmDetail, UserOption
from models.user import UserRole
from utils.exceptions import AppError
from utils.parsing import parse_optional_float


class FarmFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        on_saved: Callable[[], None],
        farm: Optional[FarmDetail] = None,
    ) -> None:
        super().__init__(master)
        self._controller = FarmController()
        self._current_user = current_user
        self._on_saved = on_saved
        self._farm = farm
        self._selected_photo_path: Optional[Path] = None
        self._owner_options: List[UserOption] = []

        self.title("Edit Farm" if farm else "Add Farm")
        self.geometry("420x680")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        self.name_entry = self._field(body, "Farm name", initial=farm.name if farm else "")

        self.owner_menu: Optional[ctk.CTkOptionMenu] = None
        if current_user.role == UserRole.ADMIN and farm is None:
            self._owner_options = self._controller.list_farm_owner_options(current_user)
            values = [self._owner_label(o) for o in self._owner_options] or ["No Farm Owner accounts yet"]
            self.owner_menu = ctk.CTkOptionMenu(body, values=values)
            self.owner_menu.pack(pady=5, fill="x")

        self.phone_entry = self._field(body, "Phone number", initial=farm.phone_number if farm else "")
        self.address_entry = self._field(body, "Address", initial=farm.address if farm else "")
        self.lat_entry = self._field(
            body,
            "GPS latitude",
            initial=str(farm.gps_latitude) if farm and farm.gps_latitude is not None else "",
        )
        self.lng_entry = self._field(
            body,
            "GPS longitude",
            initial=str(farm.gps_longitude) if farm and farm.gps_longitude is not None else "",
        )

        self.photo_label = ctk.CTkLabel(body, text=self._photo_status_text(), text_color=("gray30", "gray70"))
        self.photo_label.pack(pady=(8, 2), anchor="w")
        ctk.CTkButton(body, text="Choose Photo…", command=self._choose_photo).pack(pady=(0, 8), fill="x")

        self.notes_entry = ctk.CTkTextbox(body, height=80)
        self.notes_entry.pack(pady=5, fill="x")
        if farm and farm.notes:
            self.notes_entry.insert("1.0", farm.notes)

        self.error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"), wraplength=340)
        self.error_label.pack(pady=(8, 0))

        ctk.CTkButton(body, text="Save Farm", command=self._submit).pack(pady=(14, 0), fill="x")

    @staticmethod
    def _owner_label(option: UserOption) -> str:
        return f"{option.full_name} ({option.username})"

    def _field(self, parent: ctk.CTkFrame, placeholder: str, *, initial: str = "") -> ctk.CTkEntry:
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder)
        entry.pack(pady=5, fill="x")
        if initial:
            entry.insert(0, initial)
        return entry

    def _photo_status_text(self) -> str:
        if self._selected_photo_path is not None:
            return f"Selected: {self._selected_photo_path.name}"
        if self._farm and self._farm.photo_path:
            return "Current photo kept unless you choose a new one."
        return "No photo selected."

    def _choose_photo(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose farm photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp")],
        )
        if path:
            self._selected_photo_path = Path(path)
            self.photo_label.configure(text=self._photo_status_text())

    def _submit(self) -> None:
        try:
            latitude = parse_optional_float(self.lat_entry.get(), "GPS latitude")
            longitude = parse_optional_float(self.lng_entry.get(), "GPS longitude")
            notes = self.notes_entry.get("1.0", "end").strip()

            if self._farm is None:
                owner_id = self._resolve_selected_owner_id()
                self._controller.create_farm(
                    self._current_user,
                    name=self.name_entry.get(),
                    owner_id=owner_id,
                    phone_number=self.phone_entry.get(),
                    address=self.address_entry.get(),
                    gps_latitude=latitude,
                    gps_longitude=longitude,
                    photo_source_path=self._selected_photo_path,
                    notes=notes,
                )
            else:
                self._controller.update_farm(
                    self._current_user,
                    self._farm.id,
                    name=self.name_entry.get(),
                    phone_number=self.phone_entry.get(),
                    address=self.address_entry.get(),
                    gps_latitude=latitude,
                    gps_longitude=longitude,
                    notes=notes,
                    photo_source_path=self._selected_photo_path,
                )
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()

    def _resolve_selected_owner_id(self) -> Optional[int]:
        if self.owner_menu is None:
            return None
        selected = self.owner_menu.get()
        match = next((o for o in self._owner_options if self._owner_label(o) == selected), None)
        return match.id if match else None
