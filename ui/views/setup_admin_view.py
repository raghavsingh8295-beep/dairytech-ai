"""First-run screen: create the initial Administrator account.

Shown only when the `users` table is empty — after this, every future
account is created from the (Admin-only) User Management screen.
"""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from config.settings import settings
from controllers.auth_controller import AuthController, AuthenticatedUser, AuthenticationError
from ui.components.auth_card import AuthCard

FIELD_WIDTH = 340


class SetupAdminView(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, *, on_success: Callable[[AuthenticatedUser], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self._auth = AuthController()
        self._on_success = on_success

        card = AuthCard(self, width=420)
        body = card.body

        ctk.CTkLabel(
            body, text=f"Welcome to {settings.APP_NAME}", font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(0, 4))
        ctk.CTkLabel(
            body,
            text="Create the administrator account to get started",
            text_color=("gray30", "gray70"),
            wraplength=FIELD_WIDTH,
        ).pack(pady=(0, 18))

        self.full_name_entry = self._field(body, "Full name")
        self.username_entry = self._field(body, "Username")
        self.email_entry = self._field(body, "Email")
        self.password_entry = self._field(body, "Password", show="•")
        self.confirm_entry = self._field(body, "Confirm password", show="•")
        self.security_question_entry = self._field(
            body, "Security question (e.g. Your first pet's name?)"
        )
        self.security_answer_entry = self._field(body, "Security answer")

        self.error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"), wraplength=FIELD_WIDTH)
        self.error_label.pack(pady=(8, 0))

        ctk.CTkButton(body, text="Create Admin Account", width=FIELD_WIDTH, command=self._submit).pack(
            pady=(14, 0)
        )

    def _field(self, parent: ctk.CTkFrame, placeholder: str, *, show: str = "") -> ctk.CTkEntry:
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, width=FIELD_WIDTH, show=show)
        entry.pack(pady=5)
        return entry

    def _submit(self) -> None:
        password = self.password_entry.get()
        if password != self.confirm_entry.get():
            self.error_label.configure(text="Passwords do not match.")
            return
        try:
            user = self._auth.create_initial_admin(
                username=self.username_entry.get(),
                email=self.email_entry.get(),
                full_name=self.full_name_entry.get(),
                password=password,
                security_question=self.security_question_entry.get(),
                security_answer=self.security_answer_entry.get(),
            )
        except AuthenticationError as exc:
            self.error_label.configure(text=str(exc))
            return
        self.error_label.configure(text="")
        self._on_success(user)
