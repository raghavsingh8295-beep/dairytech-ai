"""Modal dialog for logging or editing a milk quality test.

Saving upserts by (cow, date, session). Following the lesson learned in
the Daily Recording form: since the update path is a full overwrite, this
dialog detects a collision with an existing test — on date/session change
and again at submit as a safety net — and reloads the full existing
record before allowing a save, so a targeted edit never silently wipes
other already-recorded metrics.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.milk_quality_controller import MilkQualityController, MilkQualityEntry
from models.milk_quality import MilkSession, QualityGrade
from utils.enum_utils import label_lookup
from utils.exceptions import AppError
from utils.parsing import parse_optional_date, parse_optional_float, parse_optional_int

_NOT_SPECIFIED = "Not specified"


class MilkQualityFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        cow_id: int,
        on_saved: Callable[[], None],
        test: Optional[MilkQualityEntry] = None,
    ) -> None:
        super().__init__(master)
        self._controller = MilkQualityController()
        self._current_user = current_user
        self._cow_id = cow_id
        self._on_saved = on_saved
        self._test = test

        self.title("Edit Milk Quality Test" if test else "Log Milk Quality Test")
        self.geometry("420x680")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=20)
        body = self.scroll

        self.date_entry = self._field(
            body, "Date (YYYY-MM-DD)", initial=(test.test_date if test else date.today()).isoformat()
        )

        self.session_lookup = label_lookup(MilkSession)
        self.session_menu = ctk.CTkOptionMenu(
            body, values=list(self.session_lookup), command=lambda _v: self._check_for_existing_record()
        )
        self.session_menu.set(test.session.label if test else MilkSession.COMPOSITE.label)
        self.session_menu.pack(pady=5, fill="x")

        self.existing_notice = ctk.CTkLabel(body, text="", text_color=("#b45309", "#fbbf24"))
        self.existing_notice.pack(anchor="w")

        self.fat_entry = self._field(body, "Fat %")
        self.snf_entry = self._field(body, "SNF %")
        self.protein_entry = self._field(body, "Protein %")
        self.density_entry = self._field(body, "Density (kg/m³)")
        self.bacteria_entry = self._field(body, "Bacteria count (CFU/mL)")

        self.grade_lookup = label_lookup(QualityGrade)
        grade_row = ctk.CTkFrame(body, fg_color="transparent")
        grade_row.pack(pady=5, fill="x")
        self.grade_menu = ctk.CTkOptionMenu(grade_row, values=[_NOT_SPECIFIED, *self.grade_lookup])
        self.grade_menu.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(grade_row, text="Suggest", width=80, command=self._suggest_grade).pack(
            side="left", padx=(6, 0)
        )

        self.notes_entry = ctk.CTkTextbox(body, height=70)
        self.notes_entry.pack(pady=5, fill="x")

        self.error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"), wraplength=360)
        self.error_label.pack(pady=(8, 0))

        ctk.CTkButton(body, text="Save Test", command=self._submit).pack(pady=(14, 0), fill="x")

        if test is not None:
            self._populate_from_test(test, lock_keys=True)
        else:
            self.date_entry.bind("<FocusOut>", lambda _event: self._check_for_existing_record())

    # ---- Populating from an existing test ----------------------------------

    def _populate_from_test(self, test: MilkQualityEntry, *, lock_keys: bool) -> None:
        self._test = test

        self.date_entry.configure(state="normal")
        self._set_entry(self.date_entry, test.test_date.isoformat())
        self.session_menu.set(test.session.label)
        if lock_keys:
            self.date_entry.configure(state="disabled")
            self.session_menu.configure(state="disabled")

        self._set_entry(self.fat_entry, self._num(test.fat_percent))
        self._set_entry(self.snf_entry, self._num(test.snf_percent))
        self._set_entry(self.protein_entry, self._num(test.protein_percent))
        self._set_entry(self.density_entry, self._num(test.density))
        self._set_entry(self.bacteria_entry, self._num(test.bacteria_count))
        self.grade_menu.set(test.quality_grade.label if test.quality_grade else _NOT_SPECIFIED)

        self.notes_entry.delete("1.0", "end")
        if test.notes:
            self.notes_entry.insert("1.0", test.notes)

    def _check_for_existing_record(self) -> None:
        if self._test is not None:
            return  # already resolved to an existing test; keys are locked
        test_date = parse_optional_date(self.date_entry.get(), "Date")
        if test_date is None:
            return
        session_type = self.session_lookup[self.session_menu.get()]
        existing = self._controller.get_for_date_session(
            self._current_user, self._cow_id, test_date, session_type
        )
        if existing is not None:
            self.existing_notice.configure(
                text=(
                    f"{self._article(session_type.label)} test already exists for "
                    f"{test_date.isoformat()} — editing it."
                )
            )
            self._populate_from_test(existing, lock_keys=True)

    @staticmethod
    def _article(session_label: str) -> str:
        return f"An {session_label.lower()}" if session_label[0] in "AEIOU" else f"A {session_label.lower()}"

    def _suggest_grade(self) -> None:
        fat = parse_optional_float(self.fat_entry.get(), "Fat %")
        snf = parse_optional_float(self.snf_entry.get(), "SNF %")
        bacteria = parse_optional_int(self.bacteria_entry.get(), "Bacteria count")
        suggestion = self._controller.suggest_grade(fat, snf, bacteria)
        if suggestion is None:
            self.error_label.configure(
                text="Enter Fat %, SNF %, and Bacteria count to get a grade suggestion."
            )
            return
        self.error_label.configure(text="")
        self.grade_menu.set(suggestion.label)

    @staticmethod
    def _set_entry(entry: ctk.CTkEntry, value: str) -> None:
        was_disabled = entry.cget("state") == "disabled"
        if was_disabled:
            entry.configure(state="normal")
        entry.delete(0, "end")
        if value:
            entry.insert(0, value)
        if was_disabled:
            entry.configure(state="disabled")

    @staticmethod
    def _num(value) -> str:
        return "" if value is None else str(value)

    def _field(self, parent: ctk.CTkFrame, placeholder: str, *, initial: str = "") -> ctk.CTkEntry:
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder)
        entry.pack(pady=5, fill="x")
        if initial:
            entry.insert(0, initial)
        return entry

    def _submit(self) -> None:
        try:
            test_date = parse_optional_date(self.date_entry.get(), "Date")
            if test_date is None:
                raise AppError("Date is required.")
            session_type = self.session_lookup[self.session_menu.get()]

            if self._test is None or (self._test.test_date, self._test.session) != (test_date, session_type):
                existing = self._controller.get_for_date_session(
                    self._current_user, self._cow_id, test_date, session_type
                )
                if existing is not None and (self._test is None or existing.id != self._test.id):
                    self.existing_notice.configure(
                        text=(
                            f"{self._article(session_type.label)} test already exists for "
                            f"{test_date.isoformat()} — editing it instead."
                        )
                    )
                    self._populate_from_test(existing, lock_keys=True)
                    self.error_label.configure(
                        text="Loaded the existing test for that date/session — review it and save again."
                    )
                    return

            fat = parse_optional_float(self.fat_entry.get(), "Fat %")
            snf = parse_optional_float(self.snf_entry.get(), "SNF %")
            protein = parse_optional_float(self.protein_entry.get(), "Protein %")
            density = parse_optional_float(self.density_entry.get(), "Density")
            bacteria = parse_optional_int(self.bacteria_entry.get(), "Bacteria count")

            grade_selection = self.grade_menu.get()
            grade = None if grade_selection == _NOT_SPECIFIED else self.grade_lookup[grade_selection]

            self._controller.save_test(
                self._current_user,
                cow_id=self._cow_id,
                test_date=test_date,
                session_type=session_type,
                fat_percent=fat,
                snf_percent=snf,
                protein_percent=protein,
                density=density,
                bacteria_count=bacteria,
                quality_grade=grade,
                notes=self.notes_entry.get("1.0", "end").strip(),
            )
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
