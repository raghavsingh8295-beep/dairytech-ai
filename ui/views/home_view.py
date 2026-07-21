"""Temporary landing view for the foundation build.

Real modules (Dashboard, Farms, Cows, ...) will replace this with the
sidebar-driven navigation system. For now it just proves the shell,
database, and logging are wired together correctly.
"""
from __future__ import annotations

import customtkinter as ctk

from config.settings import settings
from database.init_db import check_connection


class HomeView(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk) -> None:
        super().__init__(master, fg_color="transparent")

        title = ctk.CTkLabel(
            self,
            text=f"{settings.APP_NAME}",
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        title.pack(pady=(40, 4), padx=40, anchor="w")

        subtitle = ctk.CTkLabel(
            self,
            text=f"v{settings.APP_VERSION} — Foundation build",
            font=ctk.CTkFont(size=14),
            text_color=("gray30", "gray70"),
        )
        subtitle.pack(pady=(0, 24), padx=40, anchor="w")

        card = ctk.CTkFrame(self, corner_radius=12)
        card.pack(padx=40, fill="x")

        db_ok = check_connection()
        status_text = "Connected" if db_ok else "Connection failed"
        status_color = ("#1a7f37", "#4ade80") if db_ok else ("#b91c1c", "#f87171")

        ctk.CTkLabel(
            card, text="System Status", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=20, pady=(16, 8))

        self._status_row(card, "Database", status_text, status_color)
        self._status_row(card, "Database URL", settings.DATABASE_URL, ("gray30", "gray70"))
        self._status_row(
            card, "Next module", "Authentication (login, roles, permissions)", ("gray30", "gray70")
        )

        ctk.CTkFrame(card, height=1, fg_color=("gray80", "gray25")).pack(
            fill="x", padx=20, pady=(8, 16)
        )

    def _status_row(self, parent: ctk.CTkFrame, label: str, value: str, value_color) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row, text=label, width=140, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=value, anchor="w", text_color=value_color).pack(side="left")
