"""Modal dialog for recording or editing an income entry."""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.income_controller import IncomeController, IncomeEntry
from models.finance import IncomeCategory
from utils.enum_utils import label_lookup
from utils.exceptions import AppError
from utils.parsing import parse_optional_date, parse_optional_float

FIELD_WIDTH = 340


class IncomeFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        farm_id: int,
        on_saved: Callable[[], None],
        income: Optional[IncomeEntry] = None,
    ) -> None:
        super().__init__(master)
        self._controller = IncomeController()
        self._current_user = current_user
        self._farm_id = farm_id
        self._on_saved = on_saved
        self._income = income

        self.title("Edit Income" if income else "Record Income")
        self.geometry("400x480")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        self.category_lookup = label_lookup(IncomeCategory)
        self.category_menu = ctk.CTkOptionMenu(body, values=list(self.category_lookup))
        self.category_menu.set(income.category.label if income else IncomeCategory.MILK_SALES.label)
        self.category_menu.pack(pady=5, fill="x")

        self.amount_entry = self._field(
            body, "Amount", initial=str(income.amount) if income else ""
        )
        self.date_entry = self._field(
            body, "Date (YYYY-MM-DD)", initial=(income.income_date if income else date.today()).isoformat()
        )
        self.description_entry = self._field(
            body, "Description (e.g. buyer name)", initial=income.description if income else ""
        )

        self.notes_entry = ctk.CTkTextbox(body, height=70)
        self.notes_entry.pack(pady=5, fill="x")
        if income and income.notes:
            self.notes_entry.insert("1.0", income.notes)

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
            income_date = parse_optional_date(self.date_entry.get(), "Date")
            if income_date is None:
                raise AppError("Date is required.")
            amount = parse_optional_float(self.amount_entry.get(), "Amount")
            if amount is None:
                raise AppError("Amount is required.")
            category = self.category_lookup[self.category_menu.get()]

            kwargs = dict(
                category=category,
                amount=amount,
                income_date=income_date,
                description=self.description_entry.get(),
                notes=self.notes_entry.get("1.0", "end").strip(),
            )
            if self._income is None:
                self._controller.create_income(self._current_user, farm_id=self._farm_id, **kwargs)
            else:
                self._controller.update_income(self._current_user, self._income.id, **kwargs)
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
