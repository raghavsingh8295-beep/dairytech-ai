"""Root application window.

The sidebar/content split established here is the navigation shell every
future module plugs into: a module registers a view class, and a sidebar
button swaps it into `self.content`.
"""
from __future__ import annotations

import customtkinter as ctk

from config.settings import settings
from ui.views.home_view import HomeView
from utils.logger import get_logger

logger = get_logger(__name__)


class DairyTechApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode(settings.APPEARANCE_MODE)
        ctk.set_default_color_theme(settings.COLOR_THEME)

        self.title(settings.APP_NAME)
        self.geometry(f"{settings.WINDOW_MIN_WIDTH}x{settings.WINDOW_MIN_HEIGHT}")
        self.minsize(settings.WINDOW_MIN_WIDTH, settings.WINDOW_MIN_HEIGHT)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content_area()

        self._show_home()

        logger.info("Application window initialized.")

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nswe")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text="🐄 DairyTech AI",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(24, 32), padx=16, anchor="w")

        appearance_label = ctk.CTkLabel(sidebar, text="Appearance", anchor="w")
        appearance_label.pack(side="bottom", padx=16, pady=(0, 4), anchor="w")

        self.appearance_menu = ctk.CTkOptionMenu(
            sidebar,
            values=["System", "Light", "Dark"],
            command=self._on_appearance_change,
        )
        self.appearance_menu.set(settings.APPEARANCE_MODE)
        self.appearance_menu.pack(side="bottom", padx=16, pady=(0, 24), fill="x")

    def _build_content_area(self) -> None:
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nswe")

    def _clear_content(self) -> None:
        for widget in self.content.winfo_children():
            widget.destroy()

    def _show_home(self) -> None:
        self._clear_content()
        HomeView(self.content).pack(fill="both", expand=True)

    @staticmethod
    def _on_appearance_change(mode: str) -> None:
        ctk.set_appearance_mode(mode)
        logger.info("Appearance mode changed to %s", mode)
