"""Full daily-record history for a single cow. Reached from Cow Detail ->
"View All Records"."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.daily_record_controller import DailyRecordController, DailyRecordEntry
from ui.views.daily_record_form_dialog import DailyRecordFormDialog
from utils.exceptions import AppError
from utils.permissions import Permission, has_permission


class DailyRecordListView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        *,
        current_user: AuthenticatedUser,
        cow_id: int,
        cow_tag: str,
        on_back: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._controller = DailyRecordController()
        self._current_user = current_user
        self._cow_id = cow_id
        self._can_record = has_permission(current_user.role, Permission.RECORD_DAILY_DATA)

        ctk.CTkButton(self, text="← Back to Cow", command=on_back, fg_color="transparent").pack(
            anchor="w", padx=40, pady=(20, 0)
        )

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(8, 12))
        ctk.CTkLabel(
            header, text=f"Daily Records — #{cow_tag}", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(side="left")
        if self._can_record:
            ctk.CTkButton(header, text="+ Log New Day", command=self._open_add_dialog).pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=40, pady=(0, 24))

        self.refresh()

    def refresh(self) -> None:
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        records = self._controller.list_for_cow(self._current_user, self._cow_id)
        if not records:
            ctk.CTkLabel(
                self.list_frame, text="No daily records yet.", text_color=("gray30", "gray70")
            ).pack(pady=40)
            return

        header_row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 4))
        for text, width in (
            ("Date", 100),
            ("Milk (L)", 90),
            ("Weight", 80),
            ("Temp (°C)", 80),
            ("Heat", 60),
            ("Pregnancy", 100),
        ):
            ctk.CTkLabel(header_row, text=text, width=width, anchor="w", font=ctk.CTkFont(weight="bold")).pack(
                side="left"
            )

        for record in records:
            self._render_row(record)

    def _render_row(self, record: DailyRecordEntry) -> None:
        row = ctk.CTkFrame(self.list_frame, corner_radius=8)
        row.pack(fill="x", pady=2)

        ctk.CTkLabel(row, text=record.record_date.isoformat(), width=100, anchor="w").pack(
            side="left", padx=(10, 0), pady=8
        )
        total_milk = f"{record.total_milk_liters:g}" if record.total_milk_liters is not None else "—"
        ctk.CTkLabel(row, text=total_milk, width=90, anchor="w").pack(side="left", pady=8)
        weight = f"{record.weight_kg:g}" if record.weight_kg is not None else "—"
        ctk.CTkLabel(row, text=weight, width=80, anchor="w").pack(side="left", pady=8)
        temp = f"{record.body_temperature_c:g}" if record.body_temperature_c is not None else "—"
        ctk.CTkLabel(row, text=temp, width=80, anchor="w").pack(side="left", pady=8)
        ctk.CTkLabel(row, text="Yes" if record.heat_detected else "—", width=60, anchor="w").pack(
            side="left", pady=8
        )
        pregnancy = record.pregnancy_status.label if record.pregnancy_status else "—"
        ctk.CTkLabel(row, text=pregnancy, width=100, anchor="w").pack(side="left", pady=8)

        if self._can_record:
            ctk.CTkButton(
                row, text="Edit", width=70, command=lambda: self._edit_record(record)
            ).pack(side="right", padx=(4, 10), pady=8)
            ctk.CTkButton(
                row,
                text="Remove",
                width=70,
                fg_color="transparent",
                border_width=1,
                command=lambda: self._remove_record(record.id),
            ).pack(side="right", pady=8)

    def _open_add_dialog(self) -> None:
        DailyRecordFormDialog(
            self, current_user=self._current_user, cow_id=self._cow_id, on_saved=self.refresh
        )

    def _edit_record(self, record: DailyRecordEntry) -> None:
        DailyRecordFormDialog(
            self,
            current_user=self._current_user,
            cow_id=self._cow_id,
            on_saved=self.refresh,
            record=record,
        )

    def _remove_record(self, record_id: int) -> None:
        try:
            self._controller.delete_record(self._current_user, record_id)
        except AppError:
            pass
        self.refresh()
