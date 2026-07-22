"""Modal dialog for recording or editing a veterinarian visit."""
from __future__ import annotations

from datetime import date
from typing import Callable, List, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.disease_controller import DiseaseController, DiseaseOption
from controllers.doctor_visit_controller import DoctorVisitController, DoctorVisitEntry
from utils.exceptions import AppError
from utils.parsing import parse_optional_date, parse_optional_float

_NO_DISEASE = "Not related to a disease"
FIELD_WIDTH = 340


class DoctorVisitFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        cow_id: int,
        on_saved: Callable[[], None],
        visit: Optional[DoctorVisitEntry] = None,
    ) -> None:
        super().__init__(master)
        self._controller = DoctorVisitController()
        self._current_user = current_user
        self._cow_id = cow_id
        self._on_saved = on_saved
        self._visit = visit

        self.title("Edit Doctor Visit" if visit else "Record Doctor Visit")
        self.geometry("420x700")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=20)
        body = self.scroll

        self.vet_entry = self._field(body, "Veterinarian name", initial=visit.veterinarian_name if visit else "")
        self.date_entry = self._field(
            body, "Visit date (YYYY-MM-DD)", initial=(visit.visit_date if visit else date.today()).isoformat()
        )

        self._disease_options: List[DiseaseOption] = DiseaseController().list_options_for_cow(
            current_user, cow_id
        )
        values = [_NO_DISEASE] + [self._disease_label(o) for o in self._disease_options]
        self.disease_menu = ctk.CTkOptionMenu(body, values=values)
        selected_label = _NO_DISEASE
        if visit and visit.disease_id is not None:
            match = next((o for o in self._disease_options if o.id == visit.disease_id), None)
            if match is not None:
                selected_label = self._disease_label(match)
        self.disease_menu.set(selected_label)
        self.disease_menu.pack(pady=5, fill="x")

        self.reason_entry = self._field(body, "Reason for visit", initial=visit.reason if visit else "")
        self.diagnosis_entry = self._field(body, "Diagnosis", initial=visit.diagnosis if visit else "")
        self.recommendations_entry = self._field(
            body, "Recommendations", initial=visit.recommendations if visit else ""
        )
        self.follow_up_entry = self._field(
            body,
            "Follow-up date (YYYY-MM-DD, optional)",
            initial=visit.follow_up_date.isoformat() if visit and visit.follow_up_date else "",
        )
        self.cost_entry = self._field(
            body, "Cost", initial=str(visit.cost) if visit and visit.cost is not None else ""
        )

        self.notes_entry = ctk.CTkTextbox(body, height=70)
        self.notes_entry.pack(pady=5, fill="x")
        if visit and visit.notes:
            self.notes_entry.insert("1.0", visit.notes)

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
            visit_date = parse_optional_date(self.date_entry.get(), "Visit date")
            if visit_date is None:
                raise AppError("Visit date is required.")
            follow_up_date = parse_optional_date(self.follow_up_entry.get(), "Follow-up date")
            cost = parse_optional_float(self.cost_entry.get(), "Cost")
            notes = self.notes_entry.get("1.0", "end").strip()
            disease_id = self._resolve_selected_disease_id()

            kwargs = dict(
                veterinarian_name=self.vet_entry.get(),
                visit_date=visit_date,
                disease_id=disease_id,
                reason=self.reason_entry.get(),
                diagnosis=self.diagnosis_entry.get(),
                recommendations=self.recommendations_entry.get(),
                follow_up_date=follow_up_date,
                cost=cost,
                notes=notes,
            )

            if self._visit is None:
                self._controller.create_visit(self._current_user, cow_id=self._cow_id, **kwargs)
            else:
                self._controller.update_visit(self._current_user, self._visit.id, **kwargs)
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
