"""Dashboard — the post-login landing screen. KPI cards aggregated across
every farm the logged-in user can see (Admin: all, Farm Owner: owned,
Employee: assigned), reusing `DashboardController`'s single-query
aggregation rather than looping per farm/cow in the UI layer.
"""
from __future__ import annotations

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.dashboard_controller import DashboardController

NEUTRAL = ("gray10", "gray90")
GREEN = ("#1a7f37", "#4ade80")
RED = ("#b91c1c", "#f87171")
AMBER = ("#b45309", "#fbbf24")
BLUE = ("#2563eb", "#60a5fa")


class DashboardView(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, *, current_user: AuthenticatedUser) -> None:
        super().__init__(master, fg_color="transparent")
        self._controller = DashboardController()
        self._current_user = current_user

        ctk.CTkLabel(
            self, text=f"Welcome, {current_user.full_name}", font=ctk.CTkFont(size=28, weight="bold")
        ).pack(pady=(32, 4), padx=40, anchor="w")
        ctk.CTkLabel(
            self,
            text=f"{current_user.role.label} Dashboard",
            font=ctk.CTkFont(size=14),
            text_color=("gray30", "gray70"),
        ).pack(pady=(0, 20), padx=40, anchor="w")

        self.grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_frame.pack(fill="both", expand=True, padx=40, pady=(0, 32))
        for col in range(4):
            self.grid_frame.grid_columnconfigure(col, weight=1, uniform="card")

        self.refresh()

    def refresh(self) -> None:
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        summary = self._controller.get_dashboard(self._current_user)

        cards = [
            ("Total Farms", f"{summary.total_farms}", NEUTRAL, None),
            ("Total Cows", f"{summary.total_cows}", NEUTRAL, None),
            ("Healthy Cows", f"{summary.healthy_cows}", GREEN, None),
            (
                "Sick Cows",
                f"{summary.sick_cows}",
                RED if summary.sick_cows > 0 else NEUTRAL,
                "Needs attention" if summary.sick_cows > 0 else None,
            ),
            ("Milk Today", f"{summary.milk_today_liters:g} L", BLUE, None),
            (
                "Upcoming Vaccinations",
                f"{summary.upcoming_vaccinations}",
                AMBER if summary.upcoming_vaccinations > 0 else NEUTRAL,
                "Due within 14 days" if summary.upcoming_vaccinations > 0 else None,
            ),
            (
                "Birth Alerts",
                f"{summary.birth_alerts}",
                BLUE if summary.birth_alerts > 0 else NEUTRAL,
                "Due within 14 days" if summary.birth_alerts > 0 else None,
            ),
        ]

        if summary.revenue is not None:
            cards.append(("Revenue (this month)", f"{summary.revenue:g}", GREEN, None))
            cards.append(("Expenses (this month)", f"{summary.expenses:g}", RED, None))
            profit_color = GREEN if summary.profit >= 0 else RED
            cards.append(("Profit (this month)", f"{summary.profit:g}", profit_color, None))

        for index, (title, value, color, subtitle) in enumerate(cards):
            row, col = divmod(index, 4)
            self._render_card(row, col, title, value, color, subtitle)

    def _render_card(
        self, row: int, col: int, title: str, value: str, color: tuple, subtitle: str | None
    ) -> None:
        card = ctk.CTkFrame(self.grid_frame, corner_radius=12)
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=13), text_color=("gray30", "gray70"), anchor="w"
        ).pack(padx=18, pady=(16, 4), anchor="w")
        ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=26, weight="bold"), text_color=color, anchor="w").pack(
            padx=18, anchor="w"
        )
        if subtitle:
            ctk.CTkLabel(card, text=subtitle, font=ctk.CTkFont(size=12), text_color=color, anchor="w").pack(
                padx=18, pady=(2, 16), anchor="w"
            )
        else:
            ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=12)).pack(pady=(2, 16))
