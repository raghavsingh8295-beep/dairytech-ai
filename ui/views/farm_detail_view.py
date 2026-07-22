"""Farm detail — info, photo, GPS, employee roster."""
from __future__ import annotations

import webbrowser
from typing import Callable

import customtkinter as ctk
from PIL import Image

from config.settings import settings
from controllers.auth_controller import AuthenticatedUser
from controllers.farm_controller import FarmController
from ui.views.farm_form_dialog import FarmFormDialog
from utils.exceptions import AppError
from utils.permissions import Permission, has_permission

PHOTO_SIZE = (220, 220)


class FarmDetailView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        *,
        current_user: AuthenticatedUser,
        farm_id: int,
        on_back: Callable[[], None],
        on_open_cows: Callable[[int, str], None],
        on_open_inventory: Callable[[int, str], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._controller = FarmController()
        self._current_user = current_user
        self._farm_id = farm_id
        self._on_back = on_back
        self._on_open_cows = on_open_cows
        self._on_open_inventory = on_open_inventory
        self._can_manage = has_permission(current_user.role, Permission.MANAGE_FARMS)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=40, pady=24)

        self.refresh()

    def refresh(self) -> None:
        for widget in self.scroll.winfo_children():
            widget.destroy()

        try:
            farm = self._controller.get_farm(self._current_user, self._farm_id)
        except AppError as exc:
            ctk.CTkLabel(self.scroll, text=str(exc), text_color=("#b91c1c", "#f87171")).pack(pady=40)
            ctk.CTkButton(self.scroll, text="← Back to Farms", command=self._on_back).pack()
            return

        ctk.CTkButton(
            self.scroll, text="← Back to Farms", command=self._on_back, fg_color="transparent"
        ).pack(anchor="w", pady=(0, 12))

        header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        header.pack(fill="x")

        full_path = settings.ASSETS_DIR / farm.photo_path if farm.photo_path else None
        if full_path and full_path.exists():
            image = Image.open(full_path)
            ctk.CTkLabel(
                header, image=ctk.CTkImage(light_image=image, dark_image=image, size=PHOTO_SIZE), text=""
            ).pack(side="left", padx=(0, 20))
        else:
            ctk.CTkLabel(header, text="🐄", font=ctk.CTkFont(size=64), width=PHOTO_SIZE[0]).pack(
                side="left", padx=(0, 20)
            )

        info = ctk.CTkFrame(header, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(info, text=farm.name, font=ctk.CTkFont(size=24, weight="bold"), anchor="w").pack(
            fill="x"
        )
        ctk.CTkLabel(info, text=f"Owner: {farm.owner_name}", anchor="w").pack(fill="x", pady=(4, 0))
        if farm.phone_number:
            ctk.CTkLabel(info, text=f"Phone: {farm.phone_number}", anchor="w").pack(fill="x")
        if farm.address:
            ctk.CTkLabel(info, text=f"Address: {farm.address}", anchor="w").pack(fill="x")
        if farm.gps_latitude is not None and farm.gps_longitude is not None:
            maps_row = ctk.CTkFrame(info, fg_color="transparent")
            maps_row.pack(fill="x", pady=(2, 0))
            ctk.CTkLabel(maps_row, text=f"GPS: {farm.gps_latitude:.5f}, {farm.gps_longitude:.5f}").pack(
                side="left"
            )
            ctk.CTkButton(
                maps_row,
                text="Open in Maps",
                width=110,
                command=lambda: webbrowser.open(
                    f"https://www.google.com/maps?q={farm.gps_latitude},{farm.gps_longitude}"
                ),
            ).pack(side="left", padx=(8, 0))

        if not farm.is_active:
            ctk.CTkLabel(info, text="Inactive", text_color=("#b91c1c", "#f87171")).pack(
                anchor="w", pady=(4, 0)
            )

        if self._can_manage:
            actions = ctk.CTkFrame(header, fg_color="transparent")
            actions.pack(side="right")
            ctk.CTkButton(actions, text="Edit", width=90, command=lambda: self._edit_farm(farm)).pack(
                pady=(0, 6)
            )
            ctk.CTkButton(
                actions,
                text="Deactivate" if farm.is_active else "Inactive",
                width=90,
                fg_color="#b91c1c",
                hover_color="#7f1d1d",
                state="normal" if farm.is_active else "disabled",
                command=self._deactivate_farm,
            ).pack()

        if farm.notes:
            notes_card = ctk.CTkFrame(self.scroll, corner_radius=10)
            notes_card.pack(fill="x", pady=(20, 0))
            ctk.CTkLabel(notes_card, text="Notes", font=ctk.CTkFont(weight="bold")).pack(
                anchor="w", padx=16, pady=(12, 4)
            )
            ctk.CTkLabel(notes_card, text=farm.notes, anchor="w", justify="left", wraplength=600).pack(
                anchor="w", padx=16, pady=(0, 12)
            )

        self._render_cows_section(farm)
        self._render_inventory_section(farm)
        self._render_employees_section(farm.id)

    def _render_inventory_section(self, farm) -> None:
        section = ctk.CTkFrame(self.scroll, corner_radius=10)
        section.pack(fill="x", pady=(24, 0))

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(row, text="Inventory", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkButton(
            row,
            text="Manage Inventory",
            command=lambda: self._on_open_inventory(farm.id, farm.name),
        ).pack(side="right")

    def _render_cows_section(self, farm) -> None:
        section = ctk.CTkFrame(self.scroll, corner_radius=10)
        section.pack(fill="x", pady=(24, 0))

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(row, text="Cows", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkLabel(
            row, text=f"{farm.cow_count} registered", text_color=("gray30", "gray70")
        ).pack(side="left", padx=(10, 0))
        ctk.CTkButton(
            row, text="Manage Cows", command=lambda: self._on_open_cows(farm.id, farm.name)
        ).pack(side="right")

    def _render_employees_section(self, farm_id: int) -> None:
        section = ctk.CTkFrame(self.scroll, fg_color="transparent")
        section.pack(fill="x", pady=(24, 0))

        header_row = ctk.CTkFrame(section, fg_color="transparent")
        header_row.pack(fill="x")
        ctk.CTkLabel(header_row, text="Employees", font=ctk.CTkFont(size=18, weight="bold")).pack(
            side="left"
        )
        if self._can_manage:
            ctk.CTkButton(
                header_row, text="+ Assign Employee", command=lambda: self._open_assign_dialog(farm_id)
            ).pack(side="right")

        try:
            employees = self._controller.list_employees(self._current_user, farm_id)
        except AppError as exc:
            ctk.CTkLabel(section, text=str(exc)).pack(pady=10)
            return

        if not employees:
            ctk.CTkLabel(
                section, text="No employees assigned yet.", text_color=("gray30", "gray70")
            ).pack(anchor="w", pady=8)
            return

        for employee in employees:
            row = ctk.CTkFrame(section, corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=f"{employee.full_name} ({employee.username})", anchor="w").pack(
                side="left", padx=12, pady=8
            )
            if self._can_manage:
                ctk.CTkButton(
                    row,
                    text="Remove",
                    width=80,
                    fg_color="transparent",
                    border_width=1,
                    command=lambda e=employee: self._remove_employee(farm_id, e.id),
                ).pack(side="right", padx=12, pady=8)

    def _edit_farm(self, farm) -> None:
        FarmFormDialog(self, current_user=self._current_user, on_saved=self.refresh, farm=farm)

    def _deactivate_farm(self) -> None:
        try:
            self._controller.delete_farm(self._current_user, self._farm_id)
        except AppError:
            pass
        self.refresh()

    def _open_assign_dialog(self, farm_id: int) -> None:
        candidates = self._controller.list_assignable_employees(self._current_user, farm_id)
        dialog = ctk.CTkToplevel(self)
        dialog.title("Assign Employee")
        dialog.geometry("340x220")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        body = ctk.CTkFrame(dialog, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=20)

        if not candidates:
            ctk.CTkLabel(
                body,
                text="No unassigned Employee accounts. Create one in User Management first.",
                wraplength=280,
            ).pack(pady=20)
            return

        values = [f"{c.full_name} ({c.username})" for c in candidates]
        menu = ctk.CTkOptionMenu(body, values=values)
        menu.pack(pady=10, fill="x")

        error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"))
        error_label.pack()

        def submit() -> None:
            selected = menu.get()
            match = next((c for c in candidates if f"{c.full_name} ({c.username})" == selected), None)
            if match is None:
                return
            try:
                self._controller.assign_employee(self._current_user, farm_id=farm_id, user_id=match.id)
            except AppError as exc:
                error_label.configure(text=str(exc))
                return
            dialog.destroy()
            self.refresh()

        ctk.CTkButton(body, text="Assign", command=submit).pack(pady=(10, 0), fill="x")

    def _remove_employee(self, farm_id: int, user_id: int) -> None:
        try:
            self._controller.remove_employee(self._current_user, farm_id=farm_id, user_id=user_id)
        except AppError:
            pass
        self.refresh()
