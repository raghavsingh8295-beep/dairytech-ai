"""Modal dialog for recording or editing a heat cycle observation."""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.heat_cycle_controller import HeatCycleController, HeatCycleEntry
from utils.exceptions import AppError
from utils.parsing import parse_optional_date

FIELD_WIDTH = 340


class HeatCycleFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        cow_id: int,
        on_saved: Callable[[], None],
        heat_cycle: Optional[HeatCycleEntry] = None,
    ) -> None:
        super().__init__(master)
        self._controller = HeatCycleController()
        self._current_user = current_user
        self._cow_id = cow_id
        self._on_saved = on_saved
        self._heat_cycle = heat_cycle

        self.title("Edit Heat Cycle" if heat_cycle else "Record Heat Cycle")
        self.geometry("400x420")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        self.date_entry = self._field(
            body,
            "Heat date (YYYY-MM-DD)",
            initial=(heat_cycle.heat_date if heat_cycle else date.today()).isoformat(),
        )
        self.signs_entry = self._field(
            body, "Signs (e.g. standing heat, discharge)", initial=heat_cycle.signs if heat_cycle else ""
        )

        self.notes_entry = ctk.CTkTextbox(body, height=80)
        self.notes_entry.pack(pady=5, fill="x")
        if heat_cycle and heat_cycle.notes:
            self.notes_entry.insert("1.0", heat_cycle.notes)

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
            heat_date = parse_optional_date(self.date_entry.get(), "Heat date")
            if heat_date is None:
                raise AppError("Heat date is required.")
            signs = self.signs_entry.get()
            notes = self.notes_entry.get("1.0", "end").strip()

            if self._heat_cycle is None:
                self._controller.create_heat_cycle(
                    self._current_user, cow_id=self._cow_id, heat_date=heat_date, signs=signs, notes=notes
                )
            else:
                self._controller.update_heat_cycle(
                    self._current_user, self._heat_cycle.id, heat_date=heat_date, signs=signs, notes=notes
                )
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
