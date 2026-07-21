"""Cow roster for a single farm. Reached from Farm Detail -> "Manage Cows"."""
from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

from config.settings import settings
from controllers.auth_controller import AuthenticatedUser
from controllers.cow_controller import CowController, CowSummary
from ui.views.cow_form_dialog import CowFormDialog
from utils.permissions import Permission, has_permission

THUMB_SIZE = (64, 64)

STATUS_COLORS = {
    "healthy": ("#1a7f37", "#4ade80"),
    "sick": ("#b91c1c", "#f87171"),
    "under_treatment": ("#b45309", "#fbbf24"),
    "critical": ("#b91c1c", "#f87171"),
    "quarantined": ("#b45309", "#fbbf24"),
}


class CowListView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        *,
        current_user: AuthenticatedUser,
        farm_id: int,
        farm_name: str,
        on_open_cow: Callable[[int], None],
        on_back: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._controller = CowController()
        self._current_user = current_user
        self._farm_id = farm_id
        self._on_open_cow = on_open_cow

        ctk.CTkButton(self, text="← Back to Farm", command=on_back, fg_color="transparent").pack(
            anchor="w", padx=40, pady=(20, 0)
        )

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(8, 12))
        ctk.CTkLabel(header, text=f"Cows — {farm_name}", font=ctk.CTkFont(size=24, weight="bold")).pack(
            side="left"
        )

        if has_permission(current_user.role, Permission.MANAGE_COWS):
            ctk.CTkButton(header, text="+ Add Cow", command=self._open_add_dialog).pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=40, pady=(0, 24))

        self.refresh()

    def refresh(self) -> None:
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        cows = self._controller.list_cows(self._current_user, self._farm_id)
        if not cows:
            ctk.CTkLabel(
                self.list_frame, text="No cows registered yet.", text_color=("gray30", "gray70")
            ).pack(pady=40)
            return

        for cow in cows:
            self._render_cow_card(cow)

    def _render_cow_card(self, cow: CowSummary) -> None:
        card = ctk.CTkFrame(self.list_frame, corner_radius=10)
        card.pack(fill="x", pady=5)

        thumb = self._load_thumbnail(cow.photo_path)
        if thumb is not None:
            ctk.CTkLabel(card, image=thumb, text="").pack(side="left", padx=14, pady=12)
        else:
            ctk.CTkLabel(card, text="🐄", font=ctk.CTkFont(size=28), width=64).pack(
                side="left", padx=14, pady=12
            )

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, pady=12)
        ctk.CTkLabel(
            info, text=f"#{cow.tag_number}  ·  {cow.breed}", font=ctk.CTkFont(size=15, weight="bold"), anchor="w"
        ).pack(fill="x")

        age_text = f"{cow.age_years:g} yrs" if cow.age_years is not None else "Age unknown"
        ctk.CTkLabel(
            info, text=f"{cow.gender.label}  ·  {age_text}", anchor="w", text_color=("gray30", "gray70")
        ).pack(fill="x")

        status_row = ctk.CTkFrame(info, fg_color="transparent")
        status_row.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(
            status_row,
            text=cow.health_status.label,
            text_color=STATUS_COLORS.get(cow.health_status.value, ("gray30", "gray70")),
        ).pack(side="left")
        if cow.pregnancy_status.value == "pregnant":
            ctk.CTkLabel(status_row, text="  ·  Pregnant", text_color=("#7c3aed", "#c4b5fd")).pack(
                side="left"
            )

        if not cow.is_active:
            ctk.CTkLabel(card, text="Inactive", text_color=("#b91c1c", "#f87171")).pack(side="right", padx=10)

        ctk.CTkButton(card, text="Open", width=80, command=lambda: self._on_open_cow(cow.id)).pack(
            side="right", padx=14
        )

    def _open_add_dialog(self) -> None:
        CowFormDialog(
            self, current_user=self._current_user, farm_id=self._farm_id, on_saved=self.refresh
        )

    @staticmethod
    def _load_thumbnail(photo_path: Optional[str]) -> Optional[ctk.CTkImage]:
        if not photo_path:
            return None
        full_path = settings.ASSETS_DIR / photo_path
        if not full_path.exists():
            return None
        image = Image.open(full_path)
        return ctk.CTkImage(light_image=image, dark_image=image, size=THUMB_SIZE)
