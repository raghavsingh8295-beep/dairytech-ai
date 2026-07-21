"""Centered card container shared by the login, setup, and forgot-password screens."""
from __future__ import annotations

import customtkinter as ctk


class AuthCard(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, *, width: int = 420) -> None:
        super().__init__(master, fg_color="transparent")
        self.place(relx=0.5, rely=0.5, anchor="center")

        self.card = ctk.CTkFrame(self, width=width, corner_radius=16)
        self.card.pack()

        self.body = ctk.CTkFrame(self.card, fg_color="transparent", width=width)
        self.body.pack(fill="both", expand=True, padx=32, pady=28)
