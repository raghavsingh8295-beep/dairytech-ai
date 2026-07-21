"""Full milk-quality test history for a single cow. Reached from Cow
Detail -> "View All Tests"."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.milk_quality_controller import MilkQualityController, MilkQualityEntry
from ui.views.milk_quality_form_dialog import MilkQualityFormDialog
from utils.exceptions import AppError
from utils.permissions import Permission, has_permission

GRADE_COLORS = {
    "a": ("#1a7f37", "#4ade80"),
    "b": ("#2563eb", "#60a5fa"),
    "c": ("#b45309", "#fbbf24"),
    "rejected": ("#b91c1c", "#f87171"),
}


class MilkQualityListView(ctk.CTkFrame):
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
        self._controller = MilkQualityController()
        self._current_user = current_user
        self._cow_id = cow_id
        self._can_record = has_permission(current_user.role, Permission.RECORD_DAILY_DATA)

        ctk.CTkButton(self, text="← Back to Cow", command=on_back, fg_color="transparent").pack(
            anchor="w", padx=40, pady=(20, 0)
        )

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(8, 12))
        ctk.CTkLabel(
            header, text=f"Milk Quality — #{cow_tag}", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(side="left")
        if self._can_record:
            ctk.CTkButton(header, text="+ Log Test", command=self._open_add_dialog).pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=40, pady=(0, 24))

        self.refresh()

    def refresh(self) -> None:
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        tests = self._controller.list_for_cow(self._current_user, self._cow_id)
        if not tests:
            ctk.CTkLabel(
                self.list_frame, text="No milk quality tests yet.", text_color=("gray30", "gray70")
            ).pack(pady=40)
            return

        header_row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 4))
        for text, width in (
            ("Date", 100),
            ("Session", 90),
            ("Fat %", 60),
            ("SNF %", 60),
            ("Bacteria", 90),
            ("Grade", 110),
        ):
            ctk.CTkLabel(header_row, text=text, width=width, anchor="w", font=ctk.CTkFont(weight="bold")).pack(
                side="left"
            )

        for test in tests:
            self._render_row(test)

    def _render_row(self, test: MilkQualityEntry) -> None:
        row = ctk.CTkFrame(self.list_frame, corner_radius=8)
        row.pack(fill="x", pady=2)

        ctk.CTkLabel(row, text=test.test_date.isoformat(), width=100, anchor="w").pack(
            side="left", padx=(10, 0), pady=8
        )
        ctk.CTkLabel(row, text=test.session.label, width=90, anchor="w").pack(side="left", pady=8)
        ctk.CTkLabel(row, text=self._num(test.fat_percent), width=60, anchor="w").pack(side="left", pady=8)
        ctk.CTkLabel(row, text=self._num(test.snf_percent), width=60, anchor="w").pack(side="left", pady=8)
        bacteria = f"{test.bacteria_count:,}" if test.bacteria_count is not None else "—"
        ctk.CTkLabel(row, text=bacteria, width=90, anchor="w").pack(side="left", pady=8)

        grade_text = test.quality_grade.label if test.quality_grade else "—"
        grade_color = GRADE_COLORS.get(test.quality_grade.value, ("gray30", "gray70")) if test.quality_grade else ("gray30", "gray70")
        ctk.CTkLabel(row, text=grade_text, width=110, anchor="w", text_color=grade_color).pack(
            side="left", pady=8
        )

        if self._can_record:
            ctk.CTkButton(row, text="Edit", width=70, command=lambda: self._edit_test(test)).pack(
                side="right", padx=(4, 10), pady=8
            )
            ctk.CTkButton(
                row,
                text="Remove",
                width=70,
                fg_color="transparent",
                border_width=1,
                command=lambda: self._remove_test(test.id),
            ).pack(side="right", pady=8)

    @staticmethod
    def _num(value) -> str:
        return f"{value:g}" if value is not None else "—"

    def _open_add_dialog(self) -> None:
        MilkQualityFormDialog(
            self, current_user=self._current_user, cow_id=self._cow_id, on_saved=self.refresh
        )

    def _edit_test(self, test: MilkQualityEntry) -> None:
        MilkQualityFormDialog(
            self, current_user=self._current_user, cow_id=self._cow_id, on_saved=self.refresh, test=test
        )

    def _remove_test(self, test_id: int) -> None:
        try:
            self._controller.delete_test(self._current_user, test_id)
        except AppError:
            pass
        self.refresh()
