"""Modal dialog for logging or editing a cow's daily record.

Saving upserts by (cow, date) — there is no separate "add" vs "edit" API
call, since a farmer re-opening today's entry to add the evening milk
reading is the normal flow, not an edge case.

Because of that upsert, this dialog must never submit a blank field as
"clear this value" when an entry for the target date already exists —
that would silently wipe out whatever an earlier same-day entry recorded
(e.g. someone logs morning milk, someone else opens a fresh form later to
log the evening reading and submits without re-typing the morning value).
So whenever the target date turns out to already have a record — whether
that's the common case (default date already logged) or a manually typed,
colliding backdate — the dialog transparently switches into edit mode and
repopulates every field from that record before the user can submit.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.daily_record_controller import DailyRecordController, DailyRecordEntry
from models.cow import PregnancyStatus
from utils.enum_utils import label_lookup
from utils.exceptions import AppError
from utils.parsing import parse_optional_date, parse_optional_float, parse_optional_int

_NOT_SPECIFIED = "Not specified"


class DailyRecordFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        cow_id: int,
        on_saved: Callable[[], None],
        record: Optional[DailyRecordEntry] = None,
    ) -> None:
        super().__init__(master)
        self._controller = DailyRecordController()
        self._current_user = current_user
        self._cow_id = cow_id
        self._on_saved = on_saved
        self._record = record

        self.title("Edit Daily Record" if record else "Log Daily Record")
        self.geometry("440x800")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=20)
        body = self.scroll

        self.date_entry = self._field(
            body, "Date (YYYY-MM-DD)", initial=(record.record_date if record else date.today()).isoformat()
        )
        self.existing_notice = ctk.CTkLabel(body, text="", text_color=("#b45309", "#fbbf24"))
        self.existing_notice.pack(anchor="w")

        ctk.CTkLabel(body, text="Milk", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10, 0))
        self.milk_morning_entry = self._field(body, "Morning (L)")
        self.milk_evening_entry = self._field(body, "Evening (L)")

        ctk.CTkLabel(body, text="Vitals", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10, 0))
        self.weight_entry = self._field(body, "Weight (kg)")
        self.temperature_entry = self._field(body, "Body temperature (°C)")
        self.heart_rate_entry = self._field(body, "Heart rate (bpm)")
        self.rumination_entry = self._field(body, "Rumination (minutes)")
        self.activity_entry = self._field(body, "Activity level")
        self.bcs_entry = self._field(body, "Body condition score (1-5)")

        ctk.CTkLabel(body, text="Intake", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10, 0))
        self.feed_entry = self._field(body, "Feed intake (kg)")
        self.water_entry = self._field(body, "Water intake (L)")

        ctk.CTkLabel(body, text="Health & Breeding", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(10, 0)
        )
        self.medicine_entry = self._field(body, "Medicine given")
        self.vaccination_entry = self._field(body, "Vaccination given")
        self.disease_entry = self._field(body, "Disease / symptom note")

        self.pregnancy_lookup = label_lookup(PregnancyStatus)
        self.pregnancy_menu = ctk.CTkOptionMenu(body, values=[_NOT_SPECIFIED, *self.pregnancy_lookup])
        self.pregnancy_menu.pack(pady=5, fill="x")

        self.heat_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(body, text="Heat detected today", variable=self.heat_var).pack(anchor="w", pady=6)

        self.notes_entry = ctk.CTkTextbox(body, height=70)
        self.notes_entry.pack(pady=5, fill="x")

        self.error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"), wraplength=360)
        self.error_label.pack(pady=(8, 0))

        ctk.CTkButton(body, text="Save Record", command=self._submit).pack(pady=(14, 0), fill="x")

        if record is not None:
            self._populate_from_record(record, lock_date=True)
        else:
            self.date_entry.bind("<FocusOut>", lambda _event: self._check_for_existing_record())

    # ---- Populating from an existing record --------------------------------

    def _populate_from_record(self, record: DailyRecordEntry, *, lock_date: bool) -> None:
        self._record = record

        self.date_entry.configure(state="normal")
        self._set_entry(self.date_entry, record.record_date.isoformat())
        if lock_date:
            self.date_entry.configure(state="disabled")

        self._set_entry(self.milk_morning_entry, self._num(record.milk_morning_liters))
        self._set_entry(self.milk_evening_entry, self._num(record.milk_evening_liters))
        self._set_entry(self.weight_entry, self._num(record.weight_kg))
        self._set_entry(self.temperature_entry, self._num(record.body_temperature_c))
        self._set_entry(self.heart_rate_entry, self._num(record.heart_rate_bpm))
        self._set_entry(self.rumination_entry, self._num(record.rumination_minutes))
        self._set_entry(self.activity_entry, self._num(record.activity_level))
        self._set_entry(self.bcs_entry, self._num(record.body_condition_score))
        self._set_entry(self.feed_entry, self._num(record.feed_intake_kg))
        self._set_entry(self.water_entry, self._num(record.water_intake_liters))
        self._set_entry(self.medicine_entry, record.medicine_given or "")
        self._set_entry(self.vaccination_entry, record.vaccination_given or "")
        self._set_entry(self.disease_entry, record.disease_note or "")

        self.pregnancy_menu.set(record.pregnancy_status.label if record.pregnancy_status else _NOT_SPECIFIED)
        self.heat_var.set(bool(record.heat_detected))

        self.notes_entry.delete("1.0", "end")
        if record.notes:
            self.notes_entry.insert("1.0", record.notes)

    def _check_for_existing_record(self) -> None:
        if self._record is not None:
            return  # already resolved to an existing record; date is locked
        record_date = parse_optional_date(self.date_entry.get(), "Date")
        if record_date is None:
            return
        existing = self._controller.get_for_date(self._current_user, self._cow_id, record_date)
        if existing is not None:
            self.existing_notice.configure(
                text=f"An entry already exists for {record_date.isoformat()} — editing it."
            )
            self._populate_from_record(existing, lock_date=True)

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
            record_date = parse_optional_date(self.date_entry.get(), "Date")
            if record_date is None:
                raise AppError("Date is required.")

            # Belt-and-suspenders: if the date changed to one that already
            # has a record without the FocusOut handler catching it (e.g. a
            # fast Enter-key submit), resolve it now rather than upsert a
            # blank-field overwrite over real data.
            if self._record is None or self._record.record_date != record_date:
                existing = self._controller.get_for_date(self._current_user, self._cow_id, record_date)
                if existing is not None and (self._record is None or existing.id != self._record.id):
                    self.existing_notice.configure(
                        text=f"An entry already exists for {record_date.isoformat()} — editing it instead."
                    )
                    self._populate_from_record(existing, lock_date=True)
                    self.error_label.configure(
                        text="Loaded the existing entry for that date — review it and save again."
                    )
                    return

            milk_morning = parse_optional_float(self.milk_morning_entry.get(), "Milk morning")
            milk_evening = parse_optional_float(self.milk_evening_entry.get(), "Milk evening")
            weight = parse_optional_float(self.weight_entry.get(), "Weight")
            temperature = parse_optional_float(self.temperature_entry.get(), "Body temperature")
            heart_rate = parse_optional_int(self.heart_rate_entry.get(), "Heart rate")
            rumination = parse_optional_float(self.rumination_entry.get(), "Rumination")
            activity = parse_optional_float(self.activity_entry.get(), "Activity level")
            bcs = parse_optional_float(self.bcs_entry.get(), "Body condition score")
            feed = parse_optional_float(self.feed_entry.get(), "Feed intake")
            water = parse_optional_float(self.water_entry.get(), "Water intake")

            pregnancy_selection = self.pregnancy_menu.get()
            pregnancy_status = (
                None if pregnancy_selection == _NOT_SPECIFIED else self.pregnancy_lookup[pregnancy_selection]
            )

            self._controller.save_record(
                self._current_user,
                cow_id=self._cow_id,
                record_date=record_date,
                milk_morning_liters=milk_morning,
                milk_evening_liters=milk_evening,
                weight_kg=weight,
                body_temperature_c=temperature,
                heart_rate_bpm=heart_rate,
                rumination_minutes=rumination,
                activity_level=activity,
                feed_intake_kg=feed,
                water_intake_liters=water,
                medicine_given=self.medicine_entry.get(),
                vaccination_given=self.vaccination_entry.get(),
                disease_note=self.disease_entry.get(),
                pregnancy_status=pregnancy_status,
                heat_detected=self.heat_var.get(),
                body_condition_score=bcs,
                notes=self.notes_entry.get("1.0", "end").strip(),
            )
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
