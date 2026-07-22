"""Breeding module — tabbed view for a single cow: Heat Cycles,
Inseminations, Pregnancy Tests, Calf Births.

The Calf Births tab is where "Calf Records" becomes real: a live calf can
be registered as its own Cow via the existing Cow Management form
(`CowFormDialog`, pre-filled with breed/gender/birth date from the birth
event) rather than a duplicate calf schema.
"""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.calf_birth_controller import CalfBirthController, CalfBirthEntry
from controllers.cow_controller import CowController
from controllers.heat_cycle_controller import HeatCycleController, HeatCycleEntry
from controllers.insemination_controller import InseminationController, InseminationEntry
from controllers.pregnancy_check_controller import PregnancyCheckController, PregnancyCheckEntry
from ui.views.calf_birth_form_dialog import CalfBirthFormDialog
from ui.views.cow_form_dialog import CowFormDialog
from ui.views.heat_cycle_form_dialog import HeatCycleFormDialog
from ui.views.insemination_form_dialog import InseminationFormDialog
from ui.views.pregnancy_check_form_dialog import PregnancyCheckFormDialog
from utils.exceptions import AppError
from utils.permissions import Permission, has_permission

RESULT_COLORS = {
    "pregnant": ("#1a7f37", "#4ade80"),
    "not_pregnant": ("gray30", "gray70"),
    "inconclusive": ("#b45309", "#fbbf24"),
}

OUTCOME_COLORS = {
    "alive": ("#1a7f37", "#4ade80"),
    "stillborn": ("#b91c1c", "#f87171"),
    "died_after_birth": ("#b91c1c", "#f87171"),
}


class BreedingView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        *,
        current_user: AuthenticatedUser,
        cow_id: int,
        cow_tag: str,
        farm_id: int,
        on_back: Callable[[], None],
        on_open_cow: Callable[[int], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._current_user = current_user
        self._cow_id = cow_id
        self._farm_id = farm_id
        self._on_open_cow = on_open_cow
        self._can_manage = has_permission(current_user.role, Permission.MANAGE_BREEDING)

        self._heat_ctl = HeatCycleController()
        self._insemination_ctl = InseminationController()
        self._pregnancy_ctl = PregnancyCheckController()
        self._calf_birth_ctl = CalfBirthController()
        self._cow_ctl = CowController()
        self._mother_breed = self._cow_ctl.get_cow(current_user, cow_id).breed

        ctk.CTkButton(self, text="← Back to Cow", command=on_back, fg_color="transparent").pack(
            anchor="w", padx=40, pady=(20, 0)
        )
        ctk.CTkLabel(self, text=f"Breeding — #{cow_tag}", font=ctk.CTkFont(size=24, weight="bold")).pack(
            anchor="w", padx=40, pady=(8, 12)
        )

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=40, pady=(0, 24))
        self.tabs.add("Heat Cycles")
        self.tabs.add("Inseminations")
        self.tabs.add("Pregnancy Tests")
        self.tabs.add("Calf Births")

        self._build_heat_tab()
        self._build_insemination_tab()
        self._build_pregnancy_tab()
        self._build_calf_birth_tab()

    # ---- Heat cycles -------------------------------------------------------

    def _build_heat_tab(self) -> None:
        tab = self.tabs.tab("Heat Cycles")
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(10, 6))
        if self._can_manage:
            ctk.CTkButton(header, text="+ Record Heat", command=self._open_add_heat).pack(side="right")

        self.heat_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.heat_list.pack(fill="both", expand=True)
        self._refresh_heat()

    def _refresh_heat(self) -> None:
        for widget in self.heat_list.winfo_children():
            widget.destroy()
        records = self._heat_ctl.list_for_cow(self._current_user, self._cow_id)
        if not records:
            ctk.CTkLabel(self.heat_list, text="No heat cycle records.", text_color=("gray30", "gray70")).pack(
                pady=20
            )
            return
        for record in records:
            self._render_heat_row(record)

    def _render_heat_row(self, record: HeatCycleEntry) -> None:
        row = ctk.CTkFrame(self.heat_list, corner_radius=8)
        row.pack(fill="x", pady=3)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(info, text=record.heat_date.isoformat(), font=ctk.CTkFont(weight="bold"), anchor="w").pack(
            fill="x"
        )
        if record.signs:
            ctk.CTkLabel(info, text=record.signs, anchor="w", text_color=("gray30", "gray70")).pack(fill="x")

        if self._can_manage:
            ctk.CTkButton(row, text="Edit", width=70, command=lambda: self._open_edit_heat(record)).pack(
                side="right", padx=(4, 10), pady=8
            )
            ctk.CTkButton(
                row,
                text="Remove",
                width=70,
                fg_color="transparent",
                border_width=1,
                command=lambda: self._remove_heat(record.id),
            ).pack(side="right", pady=8)

    def _open_add_heat(self) -> None:
        HeatCycleFormDialog(self, current_user=self._current_user, cow_id=self._cow_id, on_saved=self._refresh_heat)

    def _open_edit_heat(self, record: HeatCycleEntry) -> None:
        HeatCycleFormDialog(
            self, current_user=self._current_user, cow_id=self._cow_id, on_saved=self._refresh_heat, heat_cycle=record
        )

    def _remove_heat(self, heat_cycle_id: int) -> None:
        try:
            self._heat_ctl.delete_heat_cycle(self._current_user, heat_cycle_id)
        except AppError:
            pass
        self._refresh_heat()

    # ---- Inseminations ----------------------------------------------------

    def _build_insemination_tab(self) -> None:
        tab = self.tabs.tab("Inseminations")
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(10, 6))
        if self._can_manage:
            ctk.CTkButton(header, text="+ Record Insemination", command=self._open_add_insemination).pack(
                side="right"
            )

        self.insemination_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.insemination_list.pack(fill="both", expand=True)
        self._refresh_inseminations()

    def _refresh_inseminations(self) -> None:
        for widget in self.insemination_list.winfo_children():
            widget.destroy()
        records = self._insemination_ctl.list_for_cow(self._current_user, self._cow_id)
        if not records:
            ctk.CTkLabel(
                self.insemination_list, text="No insemination records.", text_color=("gray30", "gray70")
            ).pack(pady=20)
            return
        for record in records:
            self._render_insemination_row(record)

    def _render_insemination_row(self, record: InseminationEntry) -> None:
        row = ctk.CTkFrame(self.insemination_list, corner_radius=8)
        row.pack(fill="x", pady=3)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(
            info, text=record.insemination_date.isoformat(), font=ctk.CTkFont(weight="bold"), anchor="w"
        ).pack(fill="x")
        if record.bull_semen_source:
            ctk.CTkLabel(
                info, text=record.bull_semen_source, anchor="w", text_color=("gray30", "gray70")
            ).pack(fill="x")

        if self._can_manage:
            ctk.CTkButton(
                row, text="Edit", width=70, command=lambda: self._open_edit_insemination(record)
            ).pack(side="right", padx=(4, 10), pady=8)
            ctk.CTkButton(
                row,
                text="Remove",
                width=70,
                fg_color="transparent",
                border_width=1,
                command=lambda: self._remove_insemination(record.id),
            ).pack(side="right", pady=8)

    def _open_add_insemination(self) -> None:
        InseminationFormDialog(
            self, current_user=self._current_user, cow_id=self._cow_id, on_saved=self._refresh_inseminations
        )

    def _open_edit_insemination(self, record: InseminationEntry) -> None:
        InseminationFormDialog(
            self,
            current_user=self._current_user,
            cow_id=self._cow_id,
            on_saved=self._refresh_inseminations,
            insemination=record,
        )

    def _remove_insemination(self, insemination_id: int) -> None:
        try:
            self._insemination_ctl.delete_insemination(self._current_user, insemination_id)
        except AppError:
            pass
        self._refresh_inseminations()

    # ---- Pregnancy tests ----------------------------------------------------

    def _build_pregnancy_tab(self) -> None:
        tab = self.tabs.tab("Pregnancy Tests")
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(10, 6))
        if self._can_manage:
            ctk.CTkButton(header, text="+ Record Test", command=self._open_add_pregnancy_check).pack(
                side="right"
            )

        self.pregnancy_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.pregnancy_list.pack(fill="both", expand=True)
        self._refresh_pregnancy_checks()

    def _refresh_pregnancy_checks(self) -> None:
        for widget in self.pregnancy_list.winfo_children():
            widget.destroy()
        records = self._pregnancy_ctl.list_for_cow(self._current_user, self._cow_id)
        if not records:
            ctk.CTkLabel(
                self.pregnancy_list, text="No pregnancy test records.", text_color=("gray30", "gray70")
            ).pack(pady=20)
            return
        for record in records:
            self._render_pregnancy_row(record)

    def _render_pregnancy_row(self, record: PregnancyCheckEntry) -> None:
        row = ctk.CTkFrame(self.pregnancy_list, corner_radius=8)
        row.pack(fill="x", pady=3)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(info, text=record.check_date.isoformat(), font=ctk.CTkFont(weight="bold"), anchor="w").pack(
            fill="x"
        )
        detail = record.result.label
        if record.expected_delivery_date:
            detail += f"  ·  Due {record.expected_delivery_date.isoformat()}"
        color = RESULT_COLORS.get(record.result.value, ("gray30", "gray70"))
        ctk.CTkLabel(info, text=detail, anchor="w", text_color=color).pack(fill="x")

        if self._can_manage:
            ctk.CTkButton(
                row, text="Edit", width=70, command=lambda: self._open_edit_pregnancy_check(record)
            ).pack(side="right", padx=(4, 10), pady=8)
            ctk.CTkButton(
                row,
                text="Remove",
                width=70,
                fg_color="transparent",
                border_width=1,
                command=lambda: self._remove_pregnancy_check(record.id),
            ).pack(side="right", pady=8)

    def _open_add_pregnancy_check(self) -> None:
        PregnancyCheckFormDialog(
            self, current_user=self._current_user, cow_id=self._cow_id, on_saved=self._refresh_pregnancy_checks
        )

    def _open_edit_pregnancy_check(self, record: PregnancyCheckEntry) -> None:
        PregnancyCheckFormDialog(
            self,
            current_user=self._current_user,
            cow_id=self._cow_id,
            on_saved=self._refresh_pregnancy_checks,
            check=record,
        )

    def _remove_pregnancy_check(self, check_id: int) -> None:
        try:
            self._pregnancy_ctl.delete_check(self._current_user, check_id)
        except AppError:
            pass
        self._refresh_pregnancy_checks()

    # ---- Calf births --------------------------------------------------------

    def _build_calf_birth_tab(self) -> None:
        tab = self.tabs.tab("Calf Births")
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(10, 6))
        if self._can_manage:
            ctk.CTkButton(header, text="+ Record Birth", command=self._open_add_calf_birth).pack(side="right")

        self.calf_birth_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.calf_birth_list.pack(fill="both", expand=True)
        self._refresh_calf_births()

    def _refresh_calf_births(self) -> None:
        for widget in self.calf_birth_list.winfo_children():
            widget.destroy()
        records = self._calf_birth_ctl.list_for_mother(self._current_user, self._cow_id)
        if not records:
            ctk.CTkLabel(
                self.calf_birth_list, text="No calf birth records.", text_color=("gray30", "gray70")
            ).pack(pady=20)
            return
        for record in records:
            self._render_calf_birth_row(record)

    def _render_calf_birth_row(self, record: CalfBirthEntry) -> None:
        row = ctk.CTkFrame(self.calf_birth_list, corner_radius=8)
        row.pack(fill="x", pady=3)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(
            info,
            text=f"{record.birth_date.isoformat()}  ·  {record.calf_gender.label}",
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
        ).pack(fill="x")
        color = OUTCOME_COLORS.get(record.outcome.value, ("gray30", "gray70"))
        ctk.CTkLabel(info, text=record.outcome.label, anchor="w", text_color=color).pack(fill="x")

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.pack(side="right", padx=10, pady=8)

        if record.calf_cow_id is not None:
            ctk.CTkButton(
                actions, text="View Cow", width=90, command=lambda: self._on_open_cow(record.calf_cow_id)
            ).pack(side="right")
        elif self._can_manage and record.outcome.value == "alive":
            ctk.CTkButton(
                actions, text="Register as Cow", width=120, command=lambda: self._register_calf_as_cow(record)
            ).pack(side="right")

        if self._can_manage:
            ctk.CTkButton(
                actions, text="Edit", width=70, command=lambda: self._open_edit_calf_birth(record)
            ).pack(side="right", padx=(0, 6))

    def _register_calf_as_cow(self, birth: CalfBirthEntry) -> None:
        initial_values = {
            "breed": self._mother_breed,
            "gender": birth.calf_gender,
            "birth_date": birth.birth_date.isoformat(),
        }

        def on_created(cow_id: int) -> None:
            try:
                self._calf_birth_ctl.link_calf_cow(self._current_user, birth.id, cow_id)
            except AppError:
                pass
            self._refresh_calf_births()

        CowFormDialog(
            self,
            current_user=self._current_user,
            farm_id=self._farm_id,
            on_saved=lambda: None,
            initial_values=initial_values,
            on_created=on_created,
        )

    def _open_add_calf_birth(self) -> None:
        CalfBirthFormDialog(
            self, current_user=self._current_user, mother_cow_id=self._cow_id, on_saved=self._refresh_calf_births
        )

    def _open_edit_calf_birth(self, record: CalfBirthEntry) -> None:
        CalfBirthFormDialog(
            self,
            current_user=self._current_user,
            mother_cow_id=self._cow_id,
            on_saved=self._refresh_calf_births,
            birth=record,
        )
