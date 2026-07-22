"""Modal dialog for scheduling or recording a vaccination dose.

Leaving "Date given" blank represents a scheduled/upcoming dose; filling
it in marks the dose as administered. There's no separate "mark complete"
action — editing the record and adding the date is the whole workflow.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.vaccination_controller import VaccinationController, VaccinationEntry
from utils.exceptions import AppError
from utils.parsing import parse_optional_date, parse_optional_float

FIELD_WIDTH = 340


class VaccinationFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        cow_id: int,
        on_saved: Callable[[], None],
        vaccination: Optional[VaccinationEntry] = None,
    ) -> None:
        super().__init__(master)
        self._controller = VaccinationController()
        self._current_user = current_user
        self._cow_id = cow_id
        self._on_saved = on_saved
        self._vaccination = vaccination

        self.title("Edit Vaccination" if vaccination else "Schedule / Record Vaccination")
        self.geometry("400x500")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        self.name_entry = self._field(
            body, "Vaccine name", initial=vaccination.vaccine_name if vaccination else ""
        )
        self.scheduled_entry = self._field(
            body,
            "Scheduled date (YYYY-MM-DD)",
            initial=(vaccination.scheduled_date if vaccination else date.today()).isoformat(),
        )
        self.given_entry = self._field(
            body,
            "Date given (blank = not yet given)",
            initial=vaccination.date_given.isoformat() if vaccination and vaccination.date_given else "",
        )
        self.administered_by_entry = self._field(
            body, "Administered by", initial=vaccination.administered_by if vaccination else ""
        )
        self.cost_entry = self._field(
            body, "Cost", initial=str(vaccination.cost) if vaccination and vaccination.cost is not None else ""
        )

        self.notes_entry = ctk.CTkTextbox(body, height=70)
        self.notes_entry.pack(pady=5, fill="x")
        if vaccination and vaccination.notes:
            self.notes_entry.insert("1.0", vaccination.notes)

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
            scheduled_date = parse_optional_date(self.scheduled_entry.get(), "Scheduled date")
            if scheduled_date is None:
                raise AppError("Scheduled date is required.")
            date_given = parse_optional_date(self.given_entry.get(), "Date given")
            cost = parse_optional_float(self.cost_entry.get(), "Cost")
            notes = self.notes_entry.get("1.0", "end").strip()

            if self._vaccination is None:
                self._controller.create_vaccination(
                    self._current_user,
                    cow_id=self._cow_id,
                    vaccine_name=self.name_entry.get(),
                    scheduled_date=scheduled_date,
                    date_given=date_given,
                    administered_by=self.administered_by_entry.get(),
                    cost=cost,
                    notes=notes,
                )
            else:
                self._controller.update_vaccination(
                    self._current_user,
                    self._vaccination.id,
                    vaccine_name=self.name_entry.get(),
                    scheduled_date=scheduled_date,
                    date_given=date_given,
                    administered_by=self.administered_by_entry.get(),
                    cost=cost,
                    notes=notes,
                )
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
