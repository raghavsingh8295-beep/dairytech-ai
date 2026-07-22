"""Modal dialog for recording or editing an artificial insemination event."""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.insemination_controller import InseminationController, InseminationEntry
from utils.exceptions import AppError
from utils.parsing import parse_optional_date, parse_optional_float

FIELD_WIDTH = 340


class InseminationFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        cow_id: int,
        on_saved: Callable[[], None],
        insemination: Optional[InseminationEntry] = None,
    ) -> None:
        super().__init__(master)
        self._controller = InseminationController()
        self._current_user = current_user
        self._cow_id = cow_id
        self._on_saved = on_saved
        self._insemination = insemination

        self.title("Edit Insemination" if insemination else "Record Insemination")
        self.geometry("400x480")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        self.date_entry = self._field(
            body,
            "Insemination date (YYYY-MM-DD)",
            initial=(insemination.insemination_date if insemination else date.today()).isoformat(),
        )
        self.source_entry = self._field(
            body,
            "Bull / semen source",
            initial=insemination.bull_semen_source if insemination else "",
        )
        self.technician_entry = self._field(
            body, "Technician name", initial=insemination.technician_name if insemination else ""
        )
        self.cost_entry = self._field(
            body,
            "Cost",
            initial=str(insemination.cost) if insemination and insemination.cost is not None else "",
        )

        self.notes_entry = ctk.CTkTextbox(body, height=70)
        self.notes_entry.pack(pady=5, fill="x")
        if insemination and insemination.notes:
            self.notes_entry.insert("1.0", insemination.notes)

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
            insemination_date = parse_optional_date(self.date_entry.get(), "Insemination date")
            if insemination_date is None:
                raise AppError("Insemination date is required.")
            cost = parse_optional_float(self.cost_entry.get(), "Cost")
            notes = self.notes_entry.get("1.0", "end").strip()

            kwargs = dict(
                insemination_date=insemination_date,
                bull_semen_source=self.source_entry.get(),
                technician_name=self.technician_entry.get(),
                cost=cost,
                notes=notes,
            )

            if self._insemination is None:
                self._controller.create_insemination(self._current_user, cow_id=self._cow_id, **kwargs)
            else:
                self._controller.update_insemination(self._current_user, self._insemination.id, **kwargs)
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
