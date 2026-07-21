"""Cow detail — profile, QR code, status, and edit/deactivate controls."""
from __future__ import annotations

import shutil
from datetime import date
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk
from PIL import Image

from config.settings import settings
from controllers.auth_controller import AuthenticatedUser
from controllers.cow_controller import CowController
from controllers.daily_record_controller import DailyRecordController
from controllers.milk_quality_controller import MilkQualityController
from ui.views.cow_form_dialog import CowFormDialog
from ui.views.daily_record_form_dialog import DailyRecordFormDialog
from ui.views.milk_quality_form_dialog import MilkQualityFormDialog
from utils.exceptions import AppError
from utils.permissions import Permission, has_permission

PHOTO_SIZE = (200, 200)
QR_SIZE = (140, 140)

STATUS_COLORS = {
    "healthy": ("#1a7f37", "#4ade80"),
    "sick": ("#b91c1c", "#f87171"),
    "under_treatment": ("#b45309", "#fbbf24"),
    "critical": ("#b91c1c", "#f87171"),
    "quarantined": ("#b45309", "#fbbf24"),
}


class CowDetailView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        *,
        current_user: AuthenticatedUser,
        cow_id: int,
        on_back: Callable[[], None],
        on_open_daily_records: Callable[[int, str], None],
        on_open_milk_quality: Callable[[int, str], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._controller = CowController()
        self._daily_controller = DailyRecordController()
        self._milk_quality_controller = MilkQualityController()
        self._current_user = current_user
        self._cow_id = cow_id
        self._on_back = on_back
        self._on_open_daily_records = on_open_daily_records
        self._on_open_milk_quality = on_open_milk_quality
        self._can_manage = has_permission(current_user.role, Permission.MANAGE_COWS)
        self._can_record = has_permission(current_user.role, Permission.RECORD_DAILY_DATA)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=40, pady=24)

        self.refresh()

    def refresh(self) -> None:
        for widget in self.scroll.winfo_children():
            widget.destroy()

        try:
            cow = self._controller.get_cow(self._current_user, self._cow_id)
        except AppError as exc:
            ctk.CTkLabel(self.scroll, text=str(exc), text_color=("#b91c1c", "#f87171")).pack(pady=40)
            ctk.CTkButton(self.scroll, text="← Back", command=self._on_back).pack()
            return

        ctk.CTkButton(self.scroll, text="← Back to Cows", command=self._on_back, fg_color="transparent").pack(
            anchor="w", pady=(0, 12)
        )

        header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        header.pack(fill="x")

        photo_full_path = settings.ASSETS_DIR / cow.photo_path if cow.photo_path else None
        if photo_full_path and photo_full_path.exists():
            image = Image.open(photo_full_path)
            ctk.CTkLabel(
                header, image=ctk.CTkImage(light_image=image, dark_image=image, size=PHOTO_SIZE), text=""
            ).pack(side="left", padx=(0, 20))
        else:
            ctk.CTkLabel(header, text="🐄", font=ctk.CTkFont(size=56), width=PHOTO_SIZE[0]).pack(
                side="left", padx=(0, 20)
            )

        info = ctk.CTkFrame(header, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(
            info, text=f"#{cow.tag_number}", font=ctk.CTkFont(size=24, weight="bold"), anchor="w"
        ).pack(fill="x")
        ctk.CTkLabel(info, text=cow.breed, anchor="w", text_color=("gray30", "gray70")).pack(fill="x")

        status_row = ctk.CTkFrame(info, fg_color="transparent")
        status_row.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(
            status_row,
            text=f"● {cow.health_status.label}",
            text_color=STATUS_COLORS.get(cow.health_status.value, ("gray30", "gray70")),
        ).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(status_row, text=f"Pregnancy: {cow.pregnancy_status.label}").pack(side="left")

        if not cow.is_active:
            ctk.CTkLabel(info, text="Inactive", text_color=("#b91c1c", "#f87171")).pack(
                anchor="w", pady=(4, 0)
            )

        if self._can_manage:
            actions = ctk.CTkFrame(header, fg_color="transparent")
            actions.pack(side="right")
            ctk.CTkButton(actions, text="Edit", width=90, command=lambda: self._edit_cow(cow)).pack(
                pady=(0, 6)
            )
            ctk.CTkButton(
                actions,
                text="Deactivate" if cow.is_active else "Inactive",
                width=90,
                fg_color="#b91c1c",
                hover_color="#7f1d1d",
                state="normal" if cow.is_active else "disabled",
                command=self._deactivate_cow,
            ).pack()

        self._render_facts_grid(cow)
        self._render_daily_records_section(cow)
        self._render_milk_quality_section(cow)
        self._render_qr_section(cow)

        if cow.notes:
            notes_card = ctk.CTkFrame(self.scroll, corner_radius=10)
            notes_card.pack(fill="x", pady=(20, 0))
            ctk.CTkLabel(notes_card, text="Notes", font=ctk.CTkFont(weight="bold")).pack(
                anchor="w", padx=16, pady=(12, 4)
            )
            ctk.CTkLabel(notes_card, text=cow.notes, anchor="w", justify="left", wraplength=600).pack(
                anchor="w", padx=16, pady=(0, 12)
            )

    def _render_daily_records_section(self, cow) -> None:
        card = ctk.CTkFrame(self.scroll, corner_radius=10)
        card.pack(fill="x", pady=(20, 0))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(row, text="Daily Records", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")

        recent = self._daily_controller.list_for_cow(self._current_user, cow.id, limit=1)
        last_text = f"Last logged: {recent[0].record_date.isoformat()}" if recent else "No records yet"
        ctk.CTkLabel(row, text=last_text, text_color=("gray30", "gray70")).pack(side="left", padx=(10, 0))

        if self._can_record:
            ctk.CTkButton(row, text="Log Today", width=100, command=lambda: self._log_today(cow)).pack(
                side="right", padx=(6, 0)
            )
        ctk.CTkButton(
            row,
            text="View All",
            width=90,
            fg_color="transparent",
            border_width=1,
            command=lambda: self._on_open_daily_records(cow.id, cow.tag_number),
        ).pack(side="right")

    def _log_today(self, cow) -> None:
        today_record = self._daily_controller.get_for_date(self._current_user, cow.id, date.today())
        DailyRecordFormDialog(
            self,
            current_user=self._current_user,
            cow_id=cow.id,
            on_saved=self.refresh,
            record=today_record,
        )

    def _render_milk_quality_section(self, cow) -> None:
        card = ctk.CTkFrame(self.scroll, corner_radius=10)
        card.pack(fill="x", pady=(20, 0))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(row, text="Milk Quality", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")

        recent = self._milk_quality_controller.list_for_cow(self._current_user, cow.id, limit=1)
        last_text = f"Last tested: {recent[0].test_date.isoformat()}" if recent else "No tests yet"
        ctk.CTkLabel(row, text=last_text, text_color=("gray30", "gray70")).pack(side="left", padx=(10, 0))

        if self._can_record:
            ctk.CTkButton(row, text="Log Test", width=100, command=lambda: self._open_milk_quality_dialog(cow)).pack(
                side="right", padx=(6, 0)
            )
        ctk.CTkButton(
            row,
            text="View All",
            width=90,
            fg_color="transparent",
            border_width=1,
            command=lambda: self._on_open_milk_quality(cow.id, cow.tag_number),
        ).pack(side="right")

    def _open_milk_quality_dialog(self, cow) -> None:
        MilkQualityFormDialog(self, current_user=self._current_user, cow_id=cow.id, on_saved=self.refresh)

    def _render_facts_grid(self, cow) -> None:
        card = ctk.CTkFrame(self.scroll, corner_radius=10)
        card.pack(fill="x", pady=(20, 0))
        ctk.CTkLabel(card, text="Profile", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=16, pady=(12, 4)
        )

        age_text = f"{cow.age_years:g} years" if cow.age_years is not None else "—"
        facts = [
            ("Gender", cow.gender.label),
            ("Age", age_text),
            ("Birth date", cow.birth_date.isoformat() if cow.birth_date else "—"),
            ("RFID number", cow.rfid_number or "—"),
            ("Weight", f"{cow.weight_kg:g} kg" if cow.weight_kg is not None else "—"),
            ("Height", f"{cow.height_cm:g} cm" if cow.height_cm is not None else "—"),
            ("Color", cow.color or "—"),
            ("Horn type", cow.horn_type.label if cow.horn_type else "—"),
            (
                "Expected delivery",
                cow.expected_delivery_date.isoformat() if cow.expected_delivery_date else "—",
            ),
            ("Location", cow.location or "—"),
            ("Purchase date", cow.purchase_date.isoformat() if cow.purchase_date else "—"),
            ("Purchase price", f"{cow.purchase_price:g}" if cow.purchase_price is not None else "—"),
        ]
        for label, value in facts:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(row, text=label, width=150, anchor="w", text_color=("gray30", "gray70")).pack(
                side="left"
            )
            ctk.CTkLabel(row, text=str(value), anchor="w").pack(side="left")
        ctk.CTkFrame(card, height=1, fg_color=("gray80", "gray25")).pack(fill="x", padx=16, pady=(8, 12))

    def _render_qr_section(self, cow) -> None:
        card = ctk.CTkFrame(self.scroll, corner_radius=10)
        card.pack(fill="x", pady=(20, 0))
        ctk.CTkLabel(card, text="QR Code", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=16, pady=(12, 4)
        )

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 12))

        qr_full_path = settings.ASSETS_DIR / cow.qr_code_path if cow.qr_code_path else None
        if qr_full_path and qr_full_path.exists():
            image = Image.open(qr_full_path)
            ctk.CTkLabel(
                row, image=ctk.CTkImage(light_image=image, dark_image=image, size=QR_SIZE), text=""
            ).pack(side="left", padx=(0, 16))

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left")
        ctk.CTkLabel(info, text=cow.qr_code_value, font=ctk.CTkFont(family="monospace")).pack(anchor="w")
        ctk.CTkButton(info, text="Save QR Code As…", width=160, command=lambda: self._save_qr(qr_full_path)).pack(
            anchor="w", pady=(8, 0)
        )

    def _save_qr(self, qr_full_path) -> None:
        if qr_full_path is None or not qr_full_path.exists():
            return
        dest = filedialog.asksaveasfilename(
            title="Save QR Code", defaultextension=".png", filetypes=[("PNG image", "*.png")]
        )
        if dest:
            shutil.copy(qr_full_path, dest)

    def _edit_cow(self, cow) -> None:
        CowFormDialog(
            self, current_user=self._current_user, farm_id=cow.farm_id, on_saved=self.refresh, cow=cow
        )

    def _deactivate_cow(self) -> None:
        try:
            self._controller.delete_cow(self._current_user, self._cow_id)
        except AppError:
            pass
        self.refresh()
