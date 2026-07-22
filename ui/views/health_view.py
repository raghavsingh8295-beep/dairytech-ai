"""Health module — tabbed view for a single cow: Diseases, Vaccinations,
Treatments, Doctor Visits, with a reminders banner for due/overdue items.

"Automatic Reminder" is implemented as an on-demand due/overdue query
(`VaccinationController.list_due_for_cow`, `DoctorVisitController.
list_upcoming_follow_ups_for_cow`) surfaced here, not an OS push
notification — a desktop MVC app has no background service to deliver
one. The same query methods are what a future Dashboard module would call
across every cow for its "Upcoming Vaccinations" KPI card.
"""
from __future__ import annotations

from datetime import date
from typing import Callable

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.disease_controller import DiseaseController, DiseaseEntry
from controllers.doctor_visit_controller import DoctorVisitController, DoctorVisitEntry
from controllers.treatment_controller import TreatmentController, TreatmentEntry
from controllers.vaccination_controller import VaccinationController, VaccinationEntry
from ui.views.disease_form_dialog import DiseaseFormDialog
from ui.views.doctor_visit_form_dialog import DoctorVisitFormDialog
from ui.views.treatment_form_dialog import TreatmentFormDialog
from ui.views.vaccination_form_dialog import VaccinationFormDialog
from utils.exceptions import AppError
from utils.permissions import Permission, has_permission

DISEASE_STATUS_COLORS = {
    "active": ("#b91c1c", "#f87171"),
    "recovering": ("#b45309", "#fbbf24"),
    "recovered": ("#1a7f37", "#4ade80"),
}


class HealthView(ctk.CTkFrame):
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
        self._current_user = current_user
        self._cow_id = cow_id
        self._can_manage = has_permission(current_user.role, Permission.MANAGE_HEALTH)

        self._disease_ctl = DiseaseController()
        self._vaccination_ctl = VaccinationController()
        self._treatment_ctl = TreatmentController()
        self._visit_ctl = DoctorVisitController()

        ctk.CTkButton(self, text="← Back to Cow", command=on_back, fg_color="transparent").pack(
            anchor="w", padx=40, pady=(20, 0)
        )
        ctk.CTkLabel(self, text=f"Health — #{cow_tag}", font=ctk.CTkFont(size=24, weight="bold")).pack(
            anchor="w", padx=40, pady=(8, 4)
        )

        self.reminder_label = ctk.CTkLabel(
            self, text="", text_color=("#b45309", "#fbbf24"), anchor="w", justify="left"
        )
        self.reminder_label.pack(anchor="w", padx=40, pady=(0, 12))

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=40, pady=(0, 24))
        self.tabs.add("Diseases")
        self.tabs.add("Vaccinations")
        self.tabs.add("Treatments")
        self.tabs.add("Doctor Visits")

        self._build_disease_tab()
        self._build_vaccination_tab()
        self._build_treatment_tab()
        self._build_doctor_visit_tab()

        self._refresh_reminders()

    def _refresh_reminders(self) -> None:
        due_vaccinations = self._vaccination_ctl.list_due_for_cow(self._current_user, self._cow_id)
        due_follow_ups = self._visit_ctl.list_upcoming_follow_ups_for_cow(self._current_user, self._cow_id)
        today = date.today()
        overdue_vax = [v for v in due_vaccinations if v.is_overdue(as_of=today)]
        upcoming_vax = [v for v in due_vaccinations if not v.is_overdue(as_of=today)]

        parts = []
        if overdue_vax:
            parts.append(f"⚠ {len(overdue_vax)} vaccination(s) overdue")
        if upcoming_vax:
            parts.append(f"{len(upcoming_vax)} vaccination(s) due soon")
        if due_follow_ups:
            parts.append(f"{len(due_follow_ups)} follow-up visit(s) due soon")
        self.reminder_label.configure(text="  ·  ".join(parts) if parts else "No upcoming reminders.")

    # ---- Diseases -----------------------------------------------------------

    def _build_disease_tab(self) -> None:
        tab = self.tabs.tab("Diseases")
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(10, 6))
        if self._can_manage:
            ctk.CTkButton(header, text="+ Record Disease", command=self._open_add_disease).pack(side="right")

        self.disease_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.disease_list.pack(fill="both", expand=True)
        self._refresh_diseases()

    def _refresh_diseases(self) -> None:
        for widget in self.disease_list.winfo_children():
            widget.destroy()
        diseases = self._disease_ctl.list_for_cow(self._current_user, self._cow_id)
        if not diseases:
            ctk.CTkLabel(
                self.disease_list, text="No disease records.", text_color=("gray30", "gray70")
            ).pack(pady=20)
            return
        for disease in diseases:
            self._render_disease_row(disease)

    def _render_disease_row(self, disease: DiseaseEntry) -> None:
        row = ctk.CTkFrame(self.disease_list, corner_radius=8)
        row.pack(fill="x", pady=3)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(info, text=disease.disease_name, font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x")

        color = DISEASE_STATUS_COLORS.get(disease.status.value, ("gray30", "gray70"))
        detail = (
            f"{disease.status.label}  ·  {disease.severity.label}  ·  "
            f"Diagnosed {disease.diagnosed_date.isoformat()}"
        )
        if disease.recovery_date:
            detail += f"  ·  Recovered {disease.recovery_date.isoformat()}"
        ctk.CTkLabel(info, text=detail, anchor="w", text_color=color).pack(fill="x")

        if self._can_manage:
            ctk.CTkButton(row, text="Edit", width=70, command=lambda: self._open_edit_disease(disease)).pack(
                side="right", padx=(4, 10), pady=8
            )
            ctk.CTkButton(
                row,
                text="Remove",
                width=70,
                fg_color="transparent",
                border_width=1,
                command=lambda: self._remove_disease(disease.id),
            ).pack(side="right", pady=8)

    def _open_add_disease(self) -> None:
        DiseaseFormDialog(
            self, current_user=self._current_user, cow_id=self._cow_id, on_saved=self._on_disease_saved
        )

    def _open_edit_disease(self, disease: DiseaseEntry) -> None:
        DiseaseFormDialog(
            self,
            current_user=self._current_user,
            cow_id=self._cow_id,
            on_saved=self._on_disease_saved,
            disease=disease,
        )

    def _on_disease_saved(self) -> None:
        self._refresh_diseases()
        self._refresh_reminders()

    def _remove_disease(self, disease_id: int) -> None:
        try:
            self._disease_ctl.delete_disease(self._current_user, disease_id)
        except AppError:
            pass
        self._on_disease_saved()

    # ---- Vaccinations ---------------------------------------------------

    def _build_vaccination_tab(self) -> None:
        tab = self.tabs.tab("Vaccinations")
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(10, 6))
        if self._can_manage:
            ctk.CTkButton(header, text="+ Schedule / Record", command=self._open_add_vaccination).pack(
                side="right"
            )

        self.vaccination_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.vaccination_list.pack(fill="both", expand=True)
        self._refresh_vaccinations()

    def _refresh_vaccinations(self) -> None:
        for widget in self.vaccination_list.winfo_children():
            widget.destroy()
        records = self._vaccination_ctl.list_for_cow(self._current_user, self._cow_id)
        if not records:
            ctk.CTkLabel(
                self.vaccination_list, text="No vaccination records.", text_color=("gray30", "gray70")
            ).pack(pady=20)
            return
        for record in records:
            self._render_vaccination_row(record)

    def _render_vaccination_row(self, record: VaccinationEntry) -> None:
        row = ctk.CTkFrame(self.vaccination_list, corner_radius=8)
        row.pack(fill="x", pady=3)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(info, text=record.vaccine_name, font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x")

        if record.is_completed:
            status_text, color = f"Given {record.date_given.isoformat()}", ("#1a7f37", "#4ade80")
        elif record.is_overdue(as_of=date.today()):
            status_text, color = f"Overdue since {record.scheduled_date.isoformat()}", ("#b91c1c", "#f87171")
        else:
            status_text, color = f"Scheduled {record.scheduled_date.isoformat()}", ("#2563eb", "#60a5fa")
        ctk.CTkLabel(info, text=status_text, anchor="w", text_color=color).pack(fill="x")

        if self._can_manage:
            ctk.CTkButton(
                row, text="Edit", width=70, command=lambda: self._open_edit_vaccination(record)
            ).pack(side="right", padx=(4, 10), pady=8)
            ctk.CTkButton(
                row,
                text="Remove",
                width=70,
                fg_color="transparent",
                border_width=1,
                command=lambda: self._remove_vaccination(record.id),
            ).pack(side="right", pady=8)

    def _open_add_vaccination(self) -> None:
        VaccinationFormDialog(
            self, current_user=self._current_user, cow_id=self._cow_id, on_saved=self._on_vaccination_saved
        )

    def _open_edit_vaccination(self, record: VaccinationEntry) -> None:
        VaccinationFormDialog(
            self,
            current_user=self._current_user,
            cow_id=self._cow_id,
            on_saved=self._on_vaccination_saved,
            vaccination=record,
        )

    def _on_vaccination_saved(self) -> None:
        self._refresh_vaccinations()
        self._refresh_reminders()

    def _remove_vaccination(self, vaccination_id: int) -> None:
        try:
            self._vaccination_ctl.delete_vaccination(self._current_user, vaccination_id)
        except AppError:
            pass
        self._on_vaccination_saved()

    # ---- Treatments ------------------------------------------------------

    def _build_treatment_tab(self) -> None:
        tab = self.tabs.tab("Treatments")
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(10, 6))
        if self._can_manage:
            ctk.CTkButton(header, text="+ Record Treatment", command=self._open_add_treatment).pack(
                side="right"
            )

        self.treatment_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.treatment_list.pack(fill="both", expand=True)
        self._refresh_treatments()

    def _refresh_treatments(self) -> None:
        for widget in self.treatment_list.winfo_children():
            widget.destroy()
        records = self._treatment_ctl.list_for_cow(self._current_user, self._cow_id)
        if not records:
            ctk.CTkLabel(
                self.treatment_list, text="No treatment records.", text_color=("gray30", "gray70")
            ).pack(pady=20)
            return
        for record in records:
            self._render_treatment_row(record)

    def _render_treatment_row(self, record: TreatmentEntry) -> None:
        row = ctk.CTkFrame(self.treatment_list, corner_radius=8)
        row.pack(fill="x", pady=3)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(info, text=record.medicine_name, font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x")
        detail = record.treatment_date.isoformat()
        if record.dosage:
            detail += f"  ·  {record.dosage}"
        ctk.CTkLabel(info, text=detail, anchor="w", text_color=("gray30", "gray70")).pack(fill="x")

        if self._can_manage:
            ctk.CTkButton(
                row, text="Edit", width=70, command=lambda: self._open_edit_treatment(record)
            ).pack(side="right", padx=(4, 10), pady=8)
            ctk.CTkButton(
                row,
                text="Remove",
                width=70,
                fg_color="transparent",
                border_width=1,
                command=lambda: self._remove_treatment(record.id),
            ).pack(side="right", pady=8)

    def _open_add_treatment(self) -> None:
        TreatmentFormDialog(
            self, current_user=self._current_user, cow_id=self._cow_id, on_saved=self._refresh_treatments
        )

    def _open_edit_treatment(self, record: TreatmentEntry) -> None:
        TreatmentFormDialog(
            self,
            current_user=self._current_user,
            cow_id=self._cow_id,
            on_saved=self._refresh_treatments,
            treatment=record,
        )

    def _remove_treatment(self, treatment_id: int) -> None:
        try:
            self._treatment_ctl.delete_treatment(self._current_user, treatment_id)
        except AppError:
            pass
        self._refresh_treatments()

    # ---- Doctor visits ----------------------------------------------------

    def _build_doctor_visit_tab(self) -> None:
        tab = self.tabs.tab("Doctor Visits")
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(10, 6))
        if self._can_manage:
            ctk.CTkButton(header, text="+ Record Visit", command=self._open_add_visit).pack(side="right")

        self.visit_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.visit_list.pack(fill="both", expand=True)
        self._refresh_visits()

    def _refresh_visits(self) -> None:
        for widget in self.visit_list.winfo_children():
            widget.destroy()
        records = self._visit_ctl.list_for_cow(self._current_user, self._cow_id)
        if not records:
            ctk.CTkLabel(
                self.visit_list, text="No doctor visit records.", text_color=("gray30", "gray70")
            ).pack(pady=20)
            return
        for record in records:
            self._render_visit_row(record)

    def _render_visit_row(self, record: DoctorVisitEntry) -> None:
        row = ctk.CTkFrame(self.visit_list, corner_radius=8)
        row.pack(fill="x", pady=3)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(info, text=record.veterinarian_name, font=ctk.CTkFont(weight="bold"), anchor="w").pack(
            fill="x"
        )
        detail = record.visit_date.isoformat()
        if record.reason:
            detail += f"  ·  {record.reason}"
        if record.follow_up_date:
            detail += f"  ·  Follow-up {record.follow_up_date.isoformat()}"
        ctk.CTkLabel(info, text=detail, anchor="w", text_color=("gray30", "gray70")).pack(fill="x")

        if self._can_manage:
            ctk.CTkButton(row, text="Edit", width=70, command=lambda: self._open_edit_visit(record)).pack(
                side="right", padx=(4, 10), pady=8
            )
            ctk.CTkButton(
                row,
                text="Remove",
                width=70,
                fg_color="transparent",
                border_width=1,
                command=lambda: self._remove_visit(record.id),
            ).pack(side="right", pady=8)

    def _open_add_visit(self) -> None:
        DoctorVisitFormDialog(
            self, current_user=self._current_user, cow_id=self._cow_id, on_saved=self._on_visit_saved
        )

    def _open_edit_visit(self, record: DoctorVisitEntry) -> None:
        DoctorVisitFormDialog(
            self,
            current_user=self._current_user,
            cow_id=self._cow_id,
            on_saved=self._on_visit_saved,
            visit=record,
        )

    def _on_visit_saved(self) -> None:
        self._refresh_visits()
        self._refresh_reminders()

    def _remove_visit(self, visit_id: int) -> None:
        try:
            self._visit_ctl.delete_visit(self._current_user, visit_id)
        except AppError:
            pass
        self._on_visit_saved()
