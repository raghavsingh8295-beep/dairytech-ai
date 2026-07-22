"""Modal dialog for recording or editing a pregnancy test.

If a related insemination is picked, "Suggest" fills the expected delivery
date as insemination date + 283 days (average bovine gestation) — a
starting point the farmer can adjust, the same spirit as the milk quality
grade suggestion in Module 5.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, List, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.insemination_controller import InseminationController, InseminationEntry
from controllers.pregnancy_check_controller import PregnancyCheckController, PregnancyCheckEntry
from models.breeding import PregnancyResult
from utils.enum_utils import label_lookup
from utils.exceptions import AppError
from utils.parsing import parse_optional_date

_NO_INSEMINATION = "Not linked to an insemination"
_AVERAGE_GESTATION_DAYS = 283
FIELD_WIDTH = 340


class PregnancyCheckFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        cow_id: int,
        on_saved: Callable[[], None],
        check: Optional[PregnancyCheckEntry] = None,
    ) -> None:
        super().__init__(master)
        self._controller = PregnancyCheckController()
        self._current_user = current_user
        self._cow_id = cow_id
        self._on_saved = on_saved
        self._check = check

        self.title("Edit Pregnancy Test" if check else "Record Pregnancy Test")
        self.geometry("420x600")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        self.date_entry = self._field(
            body, "Check date (YYYY-MM-DD)", initial=(check.check_date if check else date.today()).isoformat()
        )
        self.method_entry = self._field(body, "Method (e.g. Ultrasound)", initial=check.method if check else "")

        self._inseminations: List[InseminationEntry] = InseminationController().list_for_cow(
            current_user, cow_id
        )
        values = [_NO_INSEMINATION] + [self._insemination_label(i) for i in self._inseminations]
        self.insemination_menu = ctk.CTkOptionMenu(body, values=values)
        selected_label = _NO_INSEMINATION
        if check and check.insemination_id is not None:
            match = next((i for i in self._inseminations if i.id == check.insemination_id), None)
            if match is not None:
                selected_label = self._insemination_label(match)
        self.insemination_menu.set(selected_label)
        self.insemination_menu.pack(pady=5, fill="x")

        self.result_lookup = label_lookup(PregnancyResult)
        self.result_menu = ctk.CTkOptionMenu(body, values=list(self.result_lookup))
        self.result_menu.set(check.result.label if check else PregnancyResult.PREGNANT.label)
        self.result_menu.pack(pady=5, fill="x")

        delivery_row = ctk.CTkFrame(body, fg_color="transparent")
        delivery_row.pack(pady=5, fill="x")
        self.expected_delivery_entry = ctk.CTkEntry(
            delivery_row, placeholder_text="Expected delivery date (YYYY-MM-DD)"
        )
        self.expected_delivery_entry.pack(side="left", fill="x", expand=True)
        if check and check.expected_delivery_date:
            self.expected_delivery_entry.insert(0, check.expected_delivery_date.isoformat())
        ctk.CTkButton(delivery_row, text="Suggest", width=80, command=self._suggest_delivery_date).pack(
            side="left", padx=(6, 0)
        )

        self.performed_by_entry = self._field(
            body, "Performed by (vet)", initial=check.performed_by if check else ""
        )

        self.notes_entry = ctk.CTkTextbox(body, height=70)
        self.notes_entry.pack(pady=5, fill="x")
        if check and check.notes:
            self.notes_entry.insert("1.0", check.notes)

        self.error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"), wraplength=FIELD_WIDTH)
        self.error_label.pack(pady=(8, 0))

        ctk.CTkButton(body, text="Save", command=self._submit).pack(pady=(14, 0), fill="x")

    @staticmethod
    def _insemination_label(insemination: InseminationEntry) -> str:
        source = insemination.bull_semen_source or "Unknown source"
        return f"{insemination.insemination_date.isoformat()} — {source}"

    def _field(self, parent: ctk.CTkFrame, placeholder: str, *, initial: str = "") -> ctk.CTkEntry:
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder)
        entry.pack(pady=5, fill="x")
        if initial:
            entry.insert(0, initial)
        return entry

    def _resolve_selected_insemination_id(self) -> Optional[int]:
        selected = self.insemination_menu.get()
        if selected == _NO_INSEMINATION:
            return None
        match = next((i for i in self._inseminations if self._insemination_label(i) == selected), None)
        return match.id if match else None

    def _suggest_delivery_date(self) -> None:
        insemination_id = self._resolve_selected_insemination_id()
        match = next((i for i in self._inseminations if i.id == insemination_id), None)
        if match is None:
            self.error_label.configure(text="Select a related insemination first to suggest a date.")
            return
        self.error_label.configure(text="")
        suggested = match.insemination_date + timedelta(days=_AVERAGE_GESTATION_DAYS)
        self.expected_delivery_entry.delete(0, "end")
        self.expected_delivery_entry.insert(0, suggested.isoformat())

    def _submit(self) -> None:
        try:
            check_date = parse_optional_date(self.date_entry.get(), "Check date")
            if check_date is None:
                raise AppError("Check date is required.")
            expected_delivery_date = parse_optional_date(
                self.expected_delivery_entry.get(), "Expected delivery date"
            )
            result = self.result_lookup[self.result_menu.get()]
            insemination_id = self._resolve_selected_insemination_id()
            notes = self.notes_entry.get("1.0", "end").strip()

            kwargs = dict(
                check_date=check_date,
                result=result,
                insemination_id=insemination_id,
                method=self.method_entry.get(),
                expected_delivery_date=expected_delivery_date,
                performed_by=self.performed_by_entry.get(),
                notes=notes,
            )

            if self._check is None:
                self._controller.create_check(self._current_user, cow_id=self._cow_id, **kwargs)
            else:
                self._controller.update_check(self._current_user, self._check.id, **kwargs)
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
