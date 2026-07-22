"""Modal dialog for recording or editing a medicine treatment."""
from __future__ import annotations

from datetime import date
from typing import Callable, List, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.disease_controller import DiseaseController, DiseaseOption
from controllers.treatment_controller import TreatmentController, TreatmentEntry
from utils.exceptions import AppError
from utils.parsing import parse_optional_date, parse_optional_float

_NO_DISEASE = "Not related to a disease"
FIELD_WIDTH = 340


class TreatmentFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        cow_id: int,
        on_saved: Callable[[], None],
        treatment: Optional[TreatmentEntry] = None,
    ) -> None:
        super().__init__(master)
        self._controller = TreatmentController()
        self._current_user = current_user
        self._cow_id = cow_id
        self._on_saved = on_saved
        self._treatment = treatment

        self.title("Edit Treatment" if treatment else "Record Treatment")
        self.geometry("400x560")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        self.medicine_entry = self._field(
            body, "Medicine name", initial=treatment.medicine_name if treatment else ""
        )
        self.dosage_entry = self._field(body, "Dosage (e.g. 10ml)", initial=treatment.dosage if treatment else "")
        self.date_entry = self._field(
            body,
            "Treatment date (YYYY-MM-DD)",
            initial=(treatment.treatment_date if treatment else date.today()).isoformat(),
        )

        self._disease_options: List[DiseaseOption] = DiseaseController().list_options_for_cow(
            current_user, cow_id
        )
        values = [_NO_DISEASE] + [self._disease_label(o) for o in self._disease_options]
        self.disease_menu = ctk.CTkOptionMenu(body, values=values)
        selected_label = _NO_DISEASE
        if treatment and treatment.disease_id is not None:
            match = next((o for o in self._disease_options if o.id == treatment.disease_id), None)
            if match is not None:
                selected_label = self._disease_label(match)
        self.disease_menu.set(selected_label)
        self.disease_menu.pack(pady=5, fill="x")

        self.administered_by_entry = self._field(
            body, "Administered by", initial=treatment.administered_by if treatment else ""
        )
        self.cost_entry = self._field(
            body, "Cost", initial=str(treatment.cost) if treatment and treatment.cost is not None else ""
        )

        self.notes_entry = ctk.CTkTextbox(body, height=70)
        self.notes_entry.pack(pady=5, fill="x")
        if treatment and treatment.notes:
            self.notes_entry.insert("1.0", treatment.notes)

        self.error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"), wraplength=FIELD_WIDTH)
        self.error_label.pack(pady=(8, 0))

        ctk.CTkButton(body, text="Save", command=self._submit).pack(pady=(14, 0), fill="x")

    @staticmethod
    def _disease_label(option: DiseaseOption) -> str:
        return f"{option.disease_name} ({option.status.label})"

    def _field(self, parent: ctk.CTkFrame, placeholder: str, *, initial: str = "") -> ctk.CTkEntry:
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder)
        entry.pack(pady=5, fill="x")
        if initial:
            entry.insert(0, initial)
        return entry

    def _resolve_selected_disease_id(self) -> Optional[int]:
        selected = self.disease_menu.get()
        if selected == _NO_DISEASE:
            return None
        match = next((o for o in self._disease_options if self._disease_label(o) == selected), None)
        return match.id if match else None

    def _submit(self) -> None:
        try:
            treatment_date = parse_optional_date(self.date_entry.get(), "Treatment date")
            if treatment_date is None:
                raise AppError("Treatment date is required.")
            cost = parse_optional_float(self.cost_entry.get(), "Cost")
            notes = self.notes_entry.get("1.0", "end").strip()
            disease_id = self._resolve_selected_disease_id()

            if self._treatment is None:
                self._controller.create_treatment(
                    self._current_user,
                    cow_id=self._cow_id,
                    medicine_name=self.medicine_entry.get(),
                    treatment_date=treatment_date,
                    disease_id=disease_id,
                    dosage=self.dosage_entry.get(),
                    administered_by=self.administered_by_entry.get(),
                    cost=cost,
                    notes=notes,
                )
            else:
                self._controller.update_treatment(
                    self._current_user,
                    self._treatment.id,
                    medicine_name=self.medicine_entry.get(),
                    treatment_date=treatment_date,
                    disease_id=disease_id,
                    dosage=self.dosage_entry.get(),
                    administered_by=self.administered_by_entry.get(),
                    cost=cost,
                    notes=notes,
                )
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
