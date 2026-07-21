"""Admin-only screen: list accounts, create new ones, activate/deactivate."""
from __future__ import annotations

import customtkinter as ctk

from controllers.auth_controller import AuthController, AuthenticatedUser, AuthenticationError
from models.user import UserRole


class UserManagementView(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, *, current_user: AuthenticatedUser) -> None:
        super().__init__(master, fg_color="transparent")
        self._auth = AuthController()
        self._current_user = current_user

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(32, 12))
        ctk.CTkLabel(header, text="User Management", font=ctk.CTkFont(size=24, weight="bold")).pack(
            side="left"
        )
        ctk.CTkButton(header, text="+ Add User", command=self._open_add_user_dialog).pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=40, pady=(0, 24))

        self._refresh()

    def _refresh(self) -> None:
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        header_row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 4))
        for text, width in (("Username", 160), ("Full name", 200), ("Role", 120), ("Status", 90)):
            ctk.CTkLabel(header_row, text=text, width=width, anchor="w", font=ctk.CTkFont(weight="bold")).pack(
                side="left"
            )

        for user in self._auth.list_users():
            self._render_user_row(user)

    def _render_user_row(self, user: AuthenticatedUser) -> None:
        row = ctk.CTkFrame(self.list_frame, corner_radius=8)
        row.pack(fill="x", pady=3)

        ctk.CTkLabel(row, text=user.username, width=160, anchor="w").pack(side="left", padx=(10, 0), pady=8)
        ctk.CTkLabel(row, text=user.full_name, width=200, anchor="w").pack(side="left", pady=8)
        ctk.CTkLabel(row, text=user.role.label, width=120, anchor="w").pack(side="left", pady=8)

        status_text = "Active" if user.is_active else "Inactive"
        status_color = ("#1a7f37", "#4ade80") if user.is_active else ("#b91c1c", "#f87171")
        ctk.CTkLabel(row, text=status_text, width=90, anchor="w", text_color=status_color).pack(
            side="left", pady=8
        )

        is_self = user.id == self._current_user.id
        toggle_text = "Deactivate" if user.is_active else "Activate"
        ctk.CTkButton(
            row,
            text=toggle_text,
            width=100,
            state="disabled" if is_self else "normal",
            command=lambda: self._toggle_active(user),
        ).pack(side="right", padx=10, pady=8)

    def _toggle_active(self, user: AuthenticatedUser) -> None:
        try:
            self._auth.set_user_active(
                actor_role=self._current_user.role, user_id=user.id, is_active=not user.is_active
            )
        except AuthenticationError:
            pass
        self._refresh()

    def _open_add_user_dialog(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add User")
        dialog.geometry("380x520")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        body = ctk.CTkFrame(dialog, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        full_name_entry = self._field(body, "Full name")
        username_entry = self._field(body, "Username")
        email_entry = self._field(body, "Email")
        password_entry = self._field(body, "Password", show="•")
        security_question_entry = self._field(body, "Security question")
        security_answer_entry = self._field(body, "Security answer")

        role_menu = ctk.CTkOptionMenu(body, values=[UserRole.FARM_OWNER.label, UserRole.EMPLOYEE.label])
        role_menu.pack(pady=6, fill="x")

        error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"), wraplength=320)
        error_label.pack(pady=(8, 0))

        def submit() -> None:
            role_label_to_role = {role.label: role for role in UserRole}
            try:
                self._auth.register_user(
                    actor_role=self._current_user.role,
                    username=username_entry.get(),
                    email=email_entry.get(),
                    full_name=full_name_entry.get(),
                    password=password_entry.get(),
                    role=role_label_to_role[role_menu.get()],
                    security_question=security_question_entry.get(),
                    security_answer=security_answer_entry.get(),
                )
            except AuthenticationError as exc:
                error_label.configure(text=str(exc))
                return
            dialog.destroy()
            self._refresh()

        ctk.CTkButton(body, text="Create Account", command=submit).pack(pady=(16, 0), fill="x")

    def _field(self, parent: ctk.CTkFrame, placeholder: str, *, show: str = "") -> ctk.CTkEntry:
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, show=show)
        entry.pack(pady=5, fill="x")
        return entry
