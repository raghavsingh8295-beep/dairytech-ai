"""Login screen."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from config.settings import settings
from controllers.auth_controller import AuthController, AuthenticatedUser, AuthenticationError
from ui.components.auth_card import AuthCard

FIELD_WIDTH = 320


class LoginView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTk,
        *,
        on_success: Callable[[AuthenticatedUser], None],
        on_forgot_password: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._auth = AuthController()
        self._on_success = on_success
        self._on_forgot_password = on_forgot_password
        self._password_visible = False

        card = AuthCard(self, width=380)
        body = card.body

        ctk.CTkLabel(
            body, text=f"🐄 {settings.APP_NAME}", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(pady=(0, 4))
        ctk.CTkLabel(body, text="Sign in to continue", text_color=("gray30", "gray70")).pack(
            pady=(0, 20)
        )

        self.username_entry = ctk.CTkEntry(body, placeholder_text="Username", width=FIELD_WIDTH)
        self.username_entry.pack(pady=6)

        password_row = ctk.CTkFrame(body, fg_color="transparent")
        password_row.pack(pady=6)
        self.password_entry = ctk.CTkEntry(
            password_row, placeholder_text="Password", show="•", width=FIELD_WIDTH - 44
        )
        self.password_entry.pack(side="left")
        self.toggle_btn = ctk.CTkButton(
            password_row, text="Show", width=40, command=self._toggle_password
        )
        self.toggle_btn.pack(side="left", padx=(4, 0))

        self.error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"))
        self.error_label.pack(pady=(10, 0))

        ctk.CTkButton(body, text="Login", width=FIELD_WIDTH, command=self._submit).pack(
            pady=(14, 8)
        )

        forgot_link = ctk.CTkButton(
            body,
            text="Forgot password?",
            fg_color="transparent",
            hover_color=body.cget("fg_color"),
            text_color=("#2563eb", "#60a5fa"),
            command=self._on_forgot_password,
        )
        forgot_link.pack()

        self.password_entry.bind("<Return>", lambda _event: self._submit())
        self.username_entry.bind("<Return>", lambda _event: self._submit())
        self.username_entry.focus_set()

    def _toggle_password(self) -> None:
        self._password_visible = not self._password_visible
        self.password_entry.configure(show="" if self._password_visible else "•")
        self.toggle_btn.configure(text="Hide" if self._password_visible else "Show")

    def _submit(self) -> None:
        username = self.username_entry.get()
        password = self.password_entry.get()
        try:
            user = self._auth.login(username, password)
        except AuthenticationError as exc:
            self.error_label.configure(text=str(exc))
            return
        self.error_label.configure(text="")
        self._on_success(user)
