"""Forgot-password flow: username -> security question -> new password."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from controllers.auth_controller import AuthController, AuthenticationError
from ui.components.auth_card import AuthCard

FIELD_WIDTH = 320


class ForgotPasswordView(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, *, on_back_to_login: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self._auth = AuthController()
        self._on_back_to_login = on_back_to_login
        self._username = ""

        self.card = AuthCard(self, width=380)
        self._render_step_username()

    def _clear_body(self) -> ctk.CTkFrame:
        for widget in self.card.body.winfo_children():
            widget.destroy()
        return self.card.body

    def _render_step_username(self) -> None:
        body = self._clear_body()
        ctk.CTkLabel(body, text="Forgot password", font=ctk.CTkFont(size=20, weight="bold")).pack(
            pady=(0, 4)
        )
        ctk.CTkLabel(
            body, text="Enter your username to continue", text_color=("gray30", "gray70")
        ).pack(pady=(0, 18))

        self.username_entry = ctk.CTkEntry(body, placeholder_text="Username", width=FIELD_WIDTH)
        self.username_entry.pack(pady=6)
        self.username_entry.bind("<Return>", lambda _event: self._submit_username())

        self.error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"))
        self.error_label.pack(pady=(8, 0))

        ctk.CTkButton(body, text="Continue", width=FIELD_WIDTH, command=self._submit_username).pack(
            pady=(14, 8)
        )
        self._back_link(body)

    def _submit_username(self) -> None:
        username = self.username_entry.get()
        try:
            question = self._auth.get_security_question(username)
        except AuthenticationError as exc:
            self.error_label.configure(text=str(exc))
            return
        self._username = username
        self._render_step_reset(question)

    def _render_step_reset(self, question: str) -> None:
        body = self._clear_body()
        ctk.CTkLabel(body, text="Security check", font=ctk.CTkFont(size=20, weight="bold")).pack(
            pady=(0, 4)
        )
        ctk.CTkLabel(body, text=question, wraplength=FIELD_WIDTH, text_color=("gray30", "gray70")).pack(
            pady=(0, 16)
        )

        self.answer_entry = ctk.CTkEntry(body, placeholder_text="Your answer", width=FIELD_WIDTH)
        self.answer_entry.pack(pady=6)
        self.new_password_entry = ctk.CTkEntry(
            body, placeholder_text="New password", show="•", width=FIELD_WIDTH
        )
        self.new_password_entry.pack(pady=6)
        self.confirm_password_entry = ctk.CTkEntry(
            body, placeholder_text="Confirm new password", show="•", width=FIELD_WIDTH
        )
        self.confirm_password_entry.pack(pady=6)

        self.error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"), wraplength=FIELD_WIDTH)
        self.error_label.pack(pady=(8, 0))

        ctk.CTkButton(body, text="Reset Password", width=FIELD_WIDTH, command=self._submit_reset).pack(
            pady=(14, 8)
        )
        self._back_link(body)

    def _submit_reset(self) -> None:
        new_password = self.new_password_entry.get()
        if new_password != self.confirm_password_entry.get():
            self.error_label.configure(text="Passwords do not match.")
            return
        try:
            self._auth.reset_password(
                username=self._username,
                security_answer=self.answer_entry.get(),
                new_password=new_password,
            )
        except AuthenticationError as exc:
            self.error_label.configure(text=str(exc))
            return
        self._render_step_done()

    def _render_step_done(self) -> None:
        body = self._clear_body()
        ctk.CTkLabel(body, text="Password reset", font=ctk.CTkFont(size=20, weight="bold")).pack(
            pady=(0, 4)
        )
        ctk.CTkLabel(
            body,
            text="Your password has been updated. You can now sign in.",
            wraplength=FIELD_WIDTH,
            text_color=("gray30", "gray70"),
        ).pack(pady=(0, 16))
        ctk.CTkButton(body, text="Back to login", width=FIELD_WIDTH, command=self._on_back_to_login).pack()

    def _back_link(self, body: ctk.CTkFrame) -> None:
        ctk.CTkButton(
            body,
            text="Back to login",
            fg_color="transparent",
            hover_color=body.cget("fg_color"),
            text_color=("#2563eb", "#60a5fa"),
            command=self._on_back_to_login,
        ).pack()
