"""Modal dialog for recording or editing a calf birth event.

Registering the calf as its own Cow record happens separately from this
dialog — see `BreedingView._register_calf_as_cow` — since that's a
cross-module action (Cow Management) triggered from a saved birth row,
not part of logging the birth event itself.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.calf_birth_controller import CalfBirthController, CalfBirthEntry
from models.breeding import CalfOutcome
from models.cow import CowGender
from utils.enum_utils import label_lookup
from utils.exceptions import AppError
from utils.parsing import parse_optional_date, parse_optional_float

FIELD_WIDTH = 340


class CalfBirthFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        mother_cow_id: int,
        on_saved: Callable[[], None],
        birth: Optional[CalfBirthEntry] = None,
    ) -> None:
        super().__init__(master)
        self._controller = CalfBirthController()
        self._current_user = current_user
        self._mother_cow_id = mother_cow_id
        self._on_saved = on_saved
        self._birth = birth

        self.title("Edit Calf Birth" if birth else "Record Calf Birth")
        self.geometry("400x520")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        self.date_entry = self._field(
            body, "Birth date (YYYY-MM-DD)", initial=(birth.birth_date if birth else date.today()).isoformat()
        )

        self.gender_lookup = label_lookup(CowGender)
        self.gender_menu = ctk.CTkOptionMenu(body, values=list(self.gender_lookup))
        self.gender_menu.set(birth.calf_gender.label if birth else CowGender.FEMALE.label)
        self.gender_menu.pack(pady=5, fill="x")

        self.outcome_lookup = label_lookup(CalfOutcome)
        self.outcome_menu = ctk.CTkOptionMenu(body, values=list(self.outcome_lookup))
        self.outcome_menu.set(birth.outcome.label if birth else CalfOutcome.ALIVE.label)
        self.outcome_menu.pack(pady=5, fill="x")

        self.weight_entry = self._field(
            body,
            "Birth weight (kg)",
            initial=str(birth.birth_weight_kg) if birth and birth.birth_weight_kg is not None else "",
        )
        self.complications_entry = self._field(
            body, "Complications (if any)", initial=birth.complications if birth else ""
        )

        self.notes_entry = ctk.CTkTextbox(body, height=70)
        self.notes_entry.pack(pady=5, fill="x")
        if birth and birth.notes:
            self.notes_entry.insert("1.0", birth.notes)

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
            birth_date = parse_optional_date(self.date_entry.get(), "Birth date")
            if birth_date is None:
                raise AppError("Birth date is required.")
            weight = parse_optional_float(self.weight_entry.get(), "Birth weight")
            gender = self.gender_lookup[self.gender_menu.get()]
            outcome = self.outcome_lookup[self.outcome_menu.get()]
            notes = self.notes_entry.get("1.0", "end").strip()

            kwargs = dict(
                birth_date=birth_date,
                calf_gender=gender,
                outcome=outcome,
                birth_weight_kg=weight,
                complications=self.complications_entry.get(),
                notes=notes,
            )

            if self._birth is None:
                self._controller.create_birth(self._current_user, mother_cow_id=self._mother_cow_id, **kwargs)
            else:
                self._controller.update_birth(self._current_user, self._birth.id, **kwargs)
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
