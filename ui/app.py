"""Root application window.

Two modes share the same window:
  - Auth mode: SetupAdminView (first run only), LoginView, ForgotPasswordView.
    No sidebar; each view fills the window.
  - Shell mode: sidebar + content area, entered only after a successful
    login. The sidebar/content split established here is the navigation
    shell every future module plugs into.
"""
from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from config.settings import settings
from controllers.auth_controller import AuthController, AuthenticatedUser
from ui.views.forgot_password_view import ForgotPasswordView
from ui.views.home_view import HomeView
from ui.views.login_view import LoginView
from ui.views.setup_admin_view import SetupAdminView
from ui.views.user_management_view import UserManagementView
from utils.logger import get_logger
from utils.permissions import Permission, has_permission

logger = get_logger(__name__)


class DairyTechApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode(settings.APPEARANCE_MODE)
        ctk.set_default_color_theme(settings.COLOR_THEME)

        self.title(settings.APP_NAME)
        self.geometry(f"{settings.WINDOW_MIN_WIDTH}x{settings.WINDOW_MIN_HEIGHT}")
        self.minsize(settings.WINDOW_MIN_WIDTH, settings.WINDOW_MIN_HEIGHT)

        self.current_user: Optional[AuthenticatedUser] = None
        self._auth = AuthController()

        self.root_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.root_frame.pack(fill="both", expand=True)

        self._enter_auth_flow()

    # ---- Auth mode -----------------------------------------------------

    def _enter_auth_flow(self) -> None:
        self._clear(self.root_frame)
        if self._auth.has_any_users():
            self._show_login()
        else:
            self._show_setup_admin()

    def _show_setup_admin(self) -> None:
        self._clear(self.root_frame)
        SetupAdminView(self.root_frame, on_success=self._on_authenticated).pack(
            fill="both", expand=True
        )

    def _show_login(self) -> None:
        self._clear(self.root_frame)
        LoginView(
            self.root_frame,
            on_success=self._on_authenticated,
            on_forgot_password=self._show_forgot_password,
        ).pack(fill="both", expand=True)

    def _show_forgot_password(self) -> None:
        self._clear(self.root_frame)
        ForgotPasswordView(self.root_frame, on_back_to_login=self._show_login).pack(
            fill="both", expand=True
        )

    def _on_authenticated(self, user: AuthenticatedUser) -> None:
        self.current_user = user
        logger.info("Session started for %s (%s)", user.username, user.role.value)
        self._enter_shell()

    # ---- Shell mode ------------------------------------------------------

    def _enter_shell(self) -> None:
        self._clear(self.root_frame)
        self.root_frame.grid_columnconfigure(1, weight=1)
        self.root_frame.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content_area()
        self._show_home()

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self.root_frame, width=220, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nswe")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text="🐄 DairyTech AI",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(24, 8), padx=16, anchor="w")

        assert self.current_user is not None
        ctk.CTkLabel(
            sidebar,
            text=f"{self.current_user.full_name}",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(padx=16, anchor="w")
        ctk.CTkLabel(
            sidebar,
            text=self.current_user.role.label,
            font=ctk.CTkFont(size=12),
            text_color=("gray30", "gray70"),
        ).pack(padx=16, pady=(0, 20), anchor="w")

        ctk.CTkButton(sidebar, text="Home", anchor="w", command=self._show_home).pack(
            padx=16, pady=4, fill="x"
        )

        if has_permission(self.current_user.role, Permission.MANAGE_USERS):
            ctk.CTkButton(sidebar, text="Users", anchor="w", command=self._show_user_management).pack(
                padx=16, pady=4, fill="x"
            )

        ctk.CTkButton(
            sidebar,
            text="Logout",
            anchor="w",
            fg_color="transparent",
            border_width=1,
            command=self._logout,
        ).pack(side="bottom", padx=16, pady=(0, 12), fill="x")

        appearance_label = ctk.CTkLabel(sidebar, text="Appearance", anchor="w")
        appearance_label.pack(side="bottom", padx=16, pady=(0, 4), anchor="w")

        self.appearance_menu = ctk.CTkOptionMenu(
            sidebar,
            values=["System", "Light", "Dark"],
            command=self._on_appearance_change,
        )
        self.appearance_menu.set(settings.APPEARANCE_MODE)
        self.appearance_menu.pack(side="bottom", padx=16, pady=(0, 16), fill="x")

    def _build_content_area(self) -> None:
        self.content = ctk.CTkFrame(self.root_frame, corner_radius=0, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nswe")

    def _clear_content(self) -> None:
        self._clear(self.content)

    def _show_home(self) -> None:
        assert self.current_user is not None
        self._clear_content()
        HomeView(self.content, current_user=self.current_user).pack(fill="both", expand=True)

    def _show_user_management(self) -> None:
        assert self.current_user is not None
        self._clear_content()
        UserManagementView(self.content, current_user=self.current_user).pack(fill="both", expand=True)

    def _logout(self) -> None:
        logger.info("Session ended for %s", self.current_user.username if self.current_user else "unknown")
        self.current_user = None
        self._enter_auth_flow()

    # ---- Shared ----------------------------------------------------------

    @staticmethod
    def _clear(container: ctk.CTkFrame) -> None:
        for widget in container.winfo_children():
            widget.destroy()

    @staticmethod
    def _on_appearance_change(mode: str) -> None:
        ctk.set_appearance_mode(mode)
        logger.info("Appearance mode changed to %s", mode)
