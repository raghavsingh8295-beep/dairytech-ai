"""Farms list — the primary "Farms" nav screen. Visibility is scoped by
`FarmController.list_farms`: Admin sees all farms, a Farm Owner sees only
farms they own, an Employee sees only farms they're assigned to.
"""
from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

from config.settings import settings
from controllers.auth_controller import AuthenticatedUser
from controllers.farm_controller import FarmController, FarmSummary
from ui.views.farm_form_dialog import FarmFormDialog
from utils.permissions import Permission, has_permission

THUMB_SIZE = (72, 72)


class FarmListView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        *,
        current_user: AuthenticatedUser,
        on_open_farm: Callable[[int], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._controller = FarmController()
        self._current_user = current_user
        self._on_open_farm = on_open_farm

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(32, 12))
        ctk.CTkLabel(header, text="Farms", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")

        if has_permission(current_user.role, Permission.MANAGE_FARMS):
            ctk.CTkButton(header, text="+ Add Farm", command=self._open_add_dialog).pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=40, pady=(0, 24))

        self.refresh()

    def refresh(self) -> None:
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        farms = self._controller.list_farms(self._current_user)
        if not farms:
            ctk.CTkLabel(
                self.list_frame, text="No farms yet.", text_color=("gray30", "gray70")
            ).pack(pady=40)
            return

        for farm in farms:
            self._render_farm_card(farm)

    def _render_farm_card(self, farm: FarmSummary) -> None:
        card = ctk.CTkFrame(self.list_frame, corner_radius=10)
        card.pack(fill="x", pady=5)

        thumb = self._load_thumbnail(farm.photo_path)
        if thumb is not None:
            ctk.CTkLabel(card, image=thumb, text="").pack(side="left", padx=14, pady=14)
        else:
            ctk.CTkLabel(card, text="🐄", font=ctk.CTkFont(size=32), width=72).pack(
                side="left", padx=14, pady=14
            )

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, pady=14)
        ctk.CTkLabel(info, text=farm.name, font=ctk.CTkFont(size=16, weight="bold"), anchor="w").pack(
            fill="x"
        )
        ctk.CTkLabel(
            info,
            text=f"Owner: {farm.owner_name}  ·  {farm.employee_count} employee(s)",
            anchor="w",
            text_color=("gray30", "gray70"),
        ).pack(fill="x")
        if farm.address:
            ctk.CTkLabel(info, text=farm.address, anchor="w", text_color=("gray30", "gray70")).pack(fill="x")

        if not farm.is_active:
            ctk.CTkLabel(card, text="Inactive", text_color=("#b91c1c", "#f87171")).pack(side="right", padx=10)

        ctk.CTkButton(card, text="Open", width=80, command=lambda: self._on_open_farm(farm.id)).pack(
            side="right", padx=14
        )

    def _open_add_dialog(self) -> None:
        FarmFormDialog(self, current_user=self._current_user, on_saved=self.refresh)

    @staticmethod
    def _load_thumbnail(photo_path: Optional[str]) -> Optional[ctk.CTkImage]:
        if not photo_path:
            return None
        full_path = settings.ASSETS_DIR / photo_path
        if not full_path.exists():
            return None
        image = Image.open(full_path)
        return ctk.CTkImage(light_image=image, dark_image=image, size=THUMB_SIZE)
