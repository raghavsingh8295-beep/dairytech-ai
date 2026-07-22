"""Modal dialog for recording or editing a disease diagnosis.

Setting status to Recovered without a recovery date auto-fills today's
date server-side (see DiseaseController._resolve_recovery_date) — the
form doesn't need to enforce that itself.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.disease_controller import DiseaseController, DiseaseEntry
from models.health import DiseaseSeverity, DiseaseStatus
from utils.enum_utils import label_lookup
from utils.exceptions import AppError
from utils.parsing import parse_optional_date

FIELD_WIDTH = 360


class DiseaseFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        cow_id: int,
        on_saved: Callable[[], None],
        disease: Optional[DiseaseEntry] = None,
    ) -> None:
        super().__init__(master)
        self._controller = DiseaseController()
        self._current_user = current_user
        self._cow_id = cow_id
        self._on_saved = on_saved
        self._disease = disease

        self.title("Edit Disease Record" if disease else "Record Disease")
        self.geometry("420x560")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        self.name_entry = self._field(body, "Disease name", initial=disease.disease_name if disease else "")
        self.diagnosed_entry = self._field(
            body,
            "Diagnosed date (YYYY-MM-DD)",
            initial=(disease.diagnosed_date if disease else date.today()).isoformat(),
        )

        self.severity_lookup = label_lookup(DiseaseSeverity)
        self.severity_menu = ctk.CTkOptionMenu(body, values=list(self.severity_lookup))
        self.severity_menu.set(disease.severity.label if disease else DiseaseSeverity.MODERATE.label)
        self.severity_menu.pack(pady=5, fill="x")

        self.status_lookup = label_lookup(DiseaseStatus)
        self.status_menu = ctk.CTkOptionMenu(body, values=list(self.status_lookup))
        self.status_menu.set(disease.status.label if disease else DiseaseStatus.ACTIVE.label)
        self.status_menu.pack(pady=5, fill="x")

        self.recovery_entry = self._field(
            body,
            "Recovery date (YYYY-MM-DD, if recovered)",
            initial=disease.recovery_date.isoformat() if disease and disease.recovery_date else "",
        )

        self.notes_entry = ctk.CTkTextbox(body, height=80)
        self.notes_entry.pack(pady=5, fill="x")
        if disease and disease.notes:
            self.notes_entry.insert("1.0", disease.notes)

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
            diagnosed_date = parse_optional_date(self.diagnosed_entry.get(), "Diagnosed date")
            if diagnosed_date is None:
                raise AppError("Diagnosed date is required.")
            recovery_date = parse_optional_date(self.recovery_entry.get(), "Recovery date")

            severity = self.severity_lookup[self.severity_menu.get()]
            status = self.status_lookup[self.status_menu.get()]
            notes = self.notes_entry.get("1.0", "end").strip()

            if self._disease is None:
                self._controller.create_disease(
                    self._current_user,
                    cow_id=self._cow_id,
                    disease_name=self.name_entry.get(),
                    diagnosed_date=diagnosed_date,
                    severity=severity,
                    status=status,
                    recovery_date=recovery_date,
                    notes=notes,
                )
            else:
                self._controller.update_disease(
                    self._current_user,
                    self._disease.id,
                    disease_name=self.name_entry.get(),
                    diagnosed_date=diagnosed_date,
                    severity=severity,
                    status=status,
                    recovery_date=recovery_date,
                    notes=notes,
                )
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
