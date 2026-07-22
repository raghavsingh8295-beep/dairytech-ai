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
        self._password_visible = False

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
        self.password_entry, self.confirm_entry = self._password_fields(body)
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

    def _password_fields(self, parent: ctk.CTkFrame) -> tuple[ctk.CTkEntry, ctk.CTkEntry]:
        # A fully-masked password field with no way to check what actually
        # landed in it is a real trap: a wrong caps-lock state or a typo is
        # invisible until submit fails, and it's easy to retype the same
        # mistake over and over without realizing. One toggle reveals both
        # password fields together so the confirm field stays useful too.
        password_row = ctk.CTkFrame(parent, fg_color="transparent")
        password_row.pack(pady=5)
        password_entry = ctk.CTkEntry(
            password_row, placeholder_text="Password", show="•", width=FIELD_WIDTH - 60
        )
        password_entry.pack(side="left")
        self.toggle_btn = ctk.CTkButton(
            password_row, text="Show", width=52, command=self._toggle_password
        )
        self.toggle_btn.pack(side="left", padx=(6, 0))

        confirm_entry = ctk.CTkEntry(parent, placeholder_text="Confirm password", show="•", width=FIELD_WIDTH)
        confirm_entry.pack(pady=5)

        return password_entry, confirm_entry

    def _toggle_password(self) -> None:
        self._password_visible = not self._password_visible
        show = "" if self._password_visible else "•"
        self.password_entry.configure(show=show)
        self.confirm_entry.configure(show=show)
        self.toggle_btn.configure(text="Hide" if self._password_visible else "Show")

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
