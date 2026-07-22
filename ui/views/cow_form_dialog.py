"""Modal dialog for registering or editing a cow. Shared by the cow list's
"Add Cow" button, the detail view's "Edit" button, and the Breeding
module's "Register as Cow" calf-birth flow.
"""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import Callable, Optional, TypedDict

import customtkinter as ctk

from controllers.auth_controller import AuthenticatedUser
from controllers.cow_controller import CowController, CowDetail
from models.cow import CowGender, HealthStatus, HornType, PregnancyStatus
from utils.enum_utils import label_lookup
from utils.exceptions import AppError
from utils.parsing import parse_optional_date, parse_optional_float

_NOT_SPECIFIED = "Not specified"


class CowInitialValues(TypedDict, total=False):
    """Defaults to pre-fill when creating a cow from a known context (e.g.
    a calf birth already tells us breed/gender/birth date)."""

    breed: str
    gender: CowGender
    birth_date: str


class CowFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        *,
        current_user: AuthenticatedUser,
        farm_id: int,
        on_saved: Callable[[], None],
        cow: Optional[CowDetail] = None,
        initial_values: Optional[CowInitialValues] = None,
        on_created: Optional[Callable[[int], None]] = None,
    ) -> None:
        super().__init__(master)
        self._controller = CowController()
        self._current_user = current_user
        self._farm_id = farm_id
        self._on_saved = on_saved
        self._on_created = on_created
        self._cow = cow
        self._selected_photo_path: Optional[Path] = None
        defaults: CowInitialValues = {} if cow is not None else (initial_values or {})

        self.title("Edit Cow" if cow else "Add Cow")
        self.geometry("440x760")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=20)
        body = self.scroll

        self.tag_entry = self._field(body, "Tag number", initial=cow.tag_number if cow else "")
        self.rfid_entry = self._field(body, "RFID number (optional)", initial=cow.rfid_number if cow else "")
        self.breed_entry = self._field(
            body, "Breed", initial=cow.breed if cow else defaults.get("breed", "")
        )

        self.gender_lookup = label_lookup(CowGender)
        self.gender_menu = ctk.CTkOptionMenu(body, values=list(self.gender_lookup))
        default_gender = cow.gender if cow else defaults.get("gender", CowGender.FEMALE)
        self.gender_menu.set(default_gender.label)
        self.gender_menu.pack(pady=5, fill="x")

        self.birth_date_entry = self._field(
            body,
            "Birth date (YYYY-MM-DD)",
            initial=(cow.birth_date.isoformat() if cow and cow.birth_date else defaults.get("birth_date", "")),
        )
        self.weight_entry = self._field(
            body, "Weight (kg)", initial=str(cow.weight_kg) if cow and cow.weight_kg is not None else ""
        )
        self.height_entry = self._field(
            body, "Height (cm)", initial=str(cow.height_cm) if cow and cow.height_cm is not None else ""
        )
        self.color_entry = self._field(body, "Color", initial=cow.color if cow else "")

        self.horn_lookup = label_lookup(HornType)
        self.horn_menu = ctk.CTkOptionMenu(body, values=[_NOT_SPECIFIED, *self.horn_lookup])
        self.horn_menu.set(cow.horn_type.label if cow and cow.horn_type else _NOT_SPECIFIED)
        self.horn_menu.pack(pady=5, fill="x")

        self.pregnancy_lookup = label_lookup(PregnancyStatus)
        self.pregnancy_menu = ctk.CTkOptionMenu(body, values=list(self.pregnancy_lookup))
        self.pregnancy_menu.set(cow.pregnancy_status.label if cow else PregnancyStatus.OPEN.label)
        self.pregnancy_menu.pack(pady=5, fill="x")

        self.expected_delivery_entry = self._field(
            body,
            "Expected delivery date (YYYY-MM-DD)",
            initial=cow.expected_delivery_date.isoformat() if cow and cow.expected_delivery_date else "",
        )

        self.health_lookup = label_lookup(HealthStatus)
        self.health_menu = ctk.CTkOptionMenu(body, values=list(self.health_lookup))
        self.health_menu.set(cow.health_status.label if cow else HealthStatus.HEALTHY.label)
        self.health_menu.pack(pady=5, fill="x")

        self.purchase_date_entry = self._field(
            body,
            "Purchase date (YYYY-MM-DD)",
            initial=cow.purchase_date.isoformat() if cow and cow.purchase_date else "",
        )
        self.purchase_price_entry = self._field(
            body,
            "Purchase price",
            initial=str(cow.purchase_price) if cow and cow.purchase_price is not None else "",
        )
        self.location_entry = self._field(body, "Location (e.g. Barn A, Pen 3)", initial=cow.location if cow else "")

        self.photo_label = ctk.CTkLabel(body, text=self._photo_status_text(), text_color=("gray30", "gray70"))
        self.photo_label.pack(pady=(8, 2), anchor="w")
        ctk.CTkButton(body, text="Choose Photo…", command=self._choose_photo).pack(pady=(0, 8), fill="x")

        self.notes_entry = ctk.CTkTextbox(body, height=70)
        self.notes_entry.pack(pady=5, fill="x")
        if cow and cow.notes:
            self.notes_entry.insert("1.0", cow.notes)

        self.error_label = ctk.CTkLabel(body, text="", text_color=("#b91c1c", "#f87171"), wraplength=360)
        self.error_label.pack(pady=(8, 0))

        ctk.CTkButton(body, text="Save Cow", command=self._submit).pack(pady=(14, 0), fill="x")

    def _field(self, parent: ctk.CTkFrame, placeholder: str, *, initial: str = "") -> ctk.CTkEntry:
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder)
        entry.pack(pady=5, fill="x")
        if initial:
            entry.insert(0, initial)
        return entry

    def _photo_status_text(self) -> str:
        if self._selected_photo_path is not None:
            return f"Selected: {self._selected_photo_path.name}"
        if self._cow and self._cow.photo_path:
            return "Current photo kept unless you choose a new one."
        return "No photo selected."

    def _choose_photo(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose cow photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp")],
        )
        if path:
            self._selected_photo_path = Path(path)
            self.photo_label.configure(text=self._photo_status_text())

    def _submit(self) -> None:
        try:
            birth_date = parse_optional_date(self.birth_date_entry.get(), "Birth date")
            weight = parse_optional_float(self.weight_entry.get(), "Weight")
            height = parse_optional_float(self.height_entry.get(), "Height")
            expected_delivery_date = parse_optional_date(
                self.expected_delivery_entry.get(), "Expected delivery date"
            )
            purchase_date = parse_optional_date(self.purchase_date_entry.get(), "Purchase date")
            purchase_price = parse_optional_float(self.purchase_price_entry.get(), "Purchase price")

            gender = self.gender_lookup[self.gender_menu.get()]
            horn_selection = self.horn_menu.get()
            horn_type = None if horn_selection == _NOT_SPECIFIED else self.horn_lookup[horn_selection]
            pregnancy_status = self.pregnancy_lookup[self.pregnancy_menu.get()]
            health_status = self.health_lookup[self.health_menu.get()]

            kwargs = dict(
                tag_number=self.tag_entry.get(),
                rfid_number=self.rfid_entry.get(),
                breed=self.breed_entry.get(),
                gender=gender,
                birth_date=birth_date,
                weight_kg=weight,
                height_cm=height,
                color=self.color_entry.get(),
                horn_type=horn_type,
                pregnancy_status=pregnancy_status,
                expected_delivery_date=expected_delivery_date,
                health_status=health_status,
                purchase_date=purchase_date,
                purchase_price=purchase_price,
                location=self.location_entry.get(),
                notes=self.notes_entry.get("1.0", "end").strip(),
                photo_source_path=self._selected_photo_path,
            )

            created_cow_id: Optional[int] = None
            if self._cow is None:
                created = self._controller.create_cow(self._current_user, farm_id=self._farm_id, **kwargs)
                created_cow_id = created.id
            else:
                self._controller.update_cow(self._current_user, self._cow.id, **kwargs)
        except AppError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.destroy()
        self._on_saved()
        if created_cow_id is not None and self._on_created is not None:
            self._on_created(created_cow_id)
