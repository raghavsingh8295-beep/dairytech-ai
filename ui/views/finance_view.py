"""Finance module — tabbed view for a farm: Income, Expenses, Monthly
Summary. Farm-scoped, like Inventory — reached from Farm Detail.
"""
from __future__ import annotations

from datetime import date
from typing import Callable

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.expense_controller import ExpenseController, ExpenseEntry
from controllers.finance_summary_controller import FinanceSummaryController
from controllers.income_controller import IncomeController, IncomeEntry
from ui.views.expense_form_dialog import ExpenseFormDialog
from ui.views.income_form_dialog import IncomeFormDialog
from utils.exceptions import AppError
from utils.permissions import Permission, has_permission

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


class FinanceView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        *,
        current_user: AuthenticatedUser,
        farm_id: int,
        farm_name: str,
        on_back: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._income_ctl = IncomeController()
        self._expense_ctl = ExpenseController()
        self._summary_ctl = FinanceSummaryController()
        self._current_user = current_user
        self._farm_id = farm_id
        self._can_manage = has_permission(current_user.role, Permission.MANAGE_FINANCE)

        ctk.CTkButton(self, text="← Back to Farm", command=on_back, fg_color="transparent").pack(
            anchor="w", padx=40, pady=(20, 0)
        )
        ctk.CTkLabel(
            self, text=f"Finance — {farm_name}", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w", padx=40, pady=(8, 12))

        if not self._can_manage:
            ctk.CTkLabel(
                self, text="You do not have permission to view financial data.", text_color=("#b91c1c", "#f87171")
            ).pack(anchor="w", padx=40)
            return

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=40, pady=(0, 24))
        self.tabs.add("Income")
        self.tabs.add("Expenses")
        self.tabs.add("Monthly Summary")

        self._build_income_tab()
        self._build_expense_tab()
        self._build_summary_tab()

    # ---- Income -----------------------------------------------------------

    def _build_income_tab(self) -> None:
        tab = self.tabs.tab("Income")
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(10, 6))
        ctk.CTkButton(header, text="+ Record Income", command=self._open_add_income).pack(side="right")

        self.income_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.income_list.pack(fill="both", expand=True)
        self._refresh_income()

    def _refresh_income(self) -> None:
        for widget in self.income_list.winfo_children():
            widget.destroy()
        records = self._income_ctl.list_for_farm(self._current_user, self._farm_id)
        if not records:
            ctk.CTkLabel(self.income_list, text="No income recorded yet.", text_color=("gray30", "gray70")).pack(
                pady=20
            )
            return
        for record in records:
            self._render_income_row(record)

    def _render_income_row(self, record: IncomeEntry) -> None:
        row = ctk.CTkFrame(self.income_list, corner_radius=8)
        row.pack(fill="x", pady=3)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(
            info,
            text=f"{record.category.label}: {record.amount:g}",
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
            text_color=("#1a7f37", "#4ade80"),
        ).pack(fill="x")
        detail = record.income_date.isoformat()
        if record.description:
            detail += f"  ·  {record.description}"
        ctk.CTkLabel(info, text=detail, anchor="w", text_color=("gray30", "gray70")).pack(fill="x")

        ctk.CTkButton(row, text="Edit", width=70, command=lambda: self._open_edit_income(record)).pack(
            side="right", padx=(4, 10), pady=8
        )
        ctk.CTkButton(
            row,
            text="Remove",
            width=70,
            fg_color="transparent",
            border_width=1,
            command=lambda: self._remove_income(record.id),
        ).pack(side="right", pady=8)

    def _open_add_income(self) -> None:
        IncomeFormDialog(self, current_user=self._current_user, farm_id=self._farm_id, on_saved=self._refresh_income)

    def _open_edit_income(self, record: IncomeEntry) -> None:
        IncomeFormDialog(
            self, current_user=self._current_user, farm_id=self._farm_id, on_saved=self._refresh_income, income=record
        )

    def _remove_income(self, income_id: int) -> None:
        try:
            self._income_ctl.delete_income(self._current_user, income_id)
        except AppError:
            pass
        self._refresh_income()

    # ---- Expenses --------------------------------------------------------

    def _build_expense_tab(self) -> None:
        tab = self.tabs.tab("Expenses")
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(10, 6))
        ctk.CTkButton(header, text="+ Record Expense", command=self._open_add_expense).pack(side="right")

        self.expense_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.expense_list.pack(fill="both", expand=True)
        self._refresh_expenses()

    def _refresh_expenses(self) -> None:
        for widget in self.expense_list.winfo_children():
            widget.destroy()
        records = self._expense_ctl.list_for_farm(self._current_user, self._farm_id)
        if not records:
            ctk.CTkLabel(
                self.expense_list, text="No expenses recorded yet.", text_color=("gray30", "gray70")
            ).pack(pady=20)
            return
        for record in records:
            self._render_expense_row(record)

    def _render_expense_row(self, record: ExpenseEntry) -> None:
        row = ctk.CTkFrame(self.expense_list, corner_radius=8)
        row.pack(fill="x", pady=3)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(
            info,
            text=f"{record.category.label}: {record.amount:g}",
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
            text_color=("#b91c1c", "#f87171"),
        ).pack(fill="x")
        detail = record.expense_date.isoformat()
        if record.description:
            detail += f"  ·  {record.description}"
        ctk.CTkLabel(info, text=detail, anchor="w", text_color=("gray30", "gray70")).pack(fill="x")

        ctk.CTkButton(row, text="Edit", width=70, command=lambda: self._open_edit_expense(record)).pack(
            side="right", padx=(4, 10), pady=8
        )
        ctk.CTkButton(
            row,
            text="Remove",
            width=70,
            fg_color="transparent",
            border_width=1,
            command=lambda: self._remove_expense(record.id),
        ).pack(side="right", pady=8)

    def _open_add_expense(self) -> None:
        ExpenseFormDialog(
            self, current_user=self._current_user, farm_id=self._farm_id, on_saved=self._refresh_expenses
        )

    def _open_edit_expense(self, record: ExpenseEntry) -> None:
        ExpenseFormDialog(
            self,
            current_user=self._current_user,
            farm_id=self._farm_id,
            on_saved=self._refresh_expenses,
            expense=record,
        )

    def _remove_expense(self, expense_id: int) -> None:
        try:
            self._expense_ctl.delete_expense(self._current_user, expense_id)
        except AppError:
            pass
        self._refresh_expenses()

    # ---- Monthly summary ----------------------------------------------------

    def _build_summary_tab(self) -> None:
        tab = self.tabs.tab("Monthly Summary")
        today = date.today()
        self._summary_year = today.year
        self._summary_month = today.month

        picker = ctk.CTkFrame(tab, fg_color="transparent")
        picker.pack(fill="x", pady=(10, 6))
        ctk.CTkButton(picker, text="←", width=36, command=lambda: self._shift_month(-1)).pack(side="left")
        self.month_label = ctk.CTkLabel(picker, text="", font=ctk.CTkFont(weight="bold"))
        self.month_label.pack(side="left", padx=12)
        ctk.CTkButton(picker, text="→", width=36, command=lambda: self._shift_month(1)).pack(side="left")

        self.summary_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.summary_frame.pack(fill="both", expand=True, pady=(10, 0))
        self._refresh_summary()

    def _shift_month(self, delta: int) -> None:
        month = self._summary_month + delta
        year = self._summary_year
        if month < 1:
            month, year = 12, year - 1
        elif month > 12:
            month, year = 1, year + 1
        self._summary_month, self._summary_year = month, year
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        self.month_label.configure(text=f"{_MONTH_NAMES[self._summary_month - 1]} {self._summary_year}")
        for widget in self.summary_frame.winfo_children():
            widget.destroy()

        summary = self._summary_ctl.get_monthly_summary(
            self._current_user, self._farm_id, year=self._summary_year, month=self._summary_month
        )

        income_card = ctk.CTkFrame(self.summary_frame, corner_radius=10)
        income_card.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(income_card, text="Income", font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=16, pady=(12, 4)
        )
        self._summary_row(income_card, "Milk Sales", summary.milk_sales_income)
        self._summary_row(income_card, "Other Income", summary.other_income)
        self._summary_row(income_card, "Total Income", summary.total_income, bold=True)
        ctk.CTkFrame(income_card, height=1).pack(fill="x", padx=16, pady=(4, 12))

        expense_card = ctk.CTkFrame(self.summary_frame, corner_radius=10)
        expense_card.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(expense_card, text="Expenses", font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=16, pady=(12, 4)
        )
        self._summary_row(expense_card, "Feed Cost", summary.feed_cost)
        self._summary_row(expense_card, "Medicine Cost", summary.medicine_cost)
        self._summary_row(expense_card, "Other Expenses", summary.other_expenses)
        self._summary_row(expense_card, "Total Expenses", summary.total_expenses, bold=True)
        ctk.CTkFrame(expense_card, height=1).pack(fill="x", padx=16, pady=(4, 12))

        profit_card = ctk.CTkFrame(self.summary_frame, corner_radius=10)
        profit_card.pack(fill="x")
        profit_color = ("#1a7f37", "#4ade80") if summary.profit >= 0 else ("#b91c1c", "#f87171")
        row = ctk.CTkFrame(profit_card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=16)
        ctk.CTkLabel(row, text="Profit", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkLabel(
            row, text=f"{summary.profit:g}", font=ctk.CTkFont(size=18, weight="bold"), text_color=profit_color
        ).pack(side="right")

    def _summary_row(self, parent: ctk.CTkFrame, label: str, value: float, *, bold: bool = False) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=2)
        font = ctk.CTkFont(weight="bold") if bold else None
        ctk.CTkLabel(row, text=label, anchor="w", font=font).pack(side="left")
        ctk.CTkLabel(row, text=f"{value:g}", anchor="e", font=font).pack(side="right")
