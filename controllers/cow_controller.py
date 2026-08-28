"""Cow management orchestration: farm-scoped visibility (reusing the same
rules as FarmController via `controllers.farm_access`), QR code and photo
generation. Views depend only on the dataclasses below, never on `Cow`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_cow_or_raise, get_farm_or_raise
from database.session import get_db_session
from models.cow import Cow, CowGender, HealthStatus, HornType, PregnancyStatus
from services.cow_service import CowService
from services.farm_service import FarmService
from utils.exceptions import AppError
from utils.file_storage import delete_image, save_image
from utils.permissions import Permission
from utils.qr_code import generate_qr_image, generate_qr_value
from utils.validators import validate_non_negative


class CowError(AppError):
    """Raised for any cow-related failure the UI should surface."""


@dataclass(frozen=True)
class CowSummary:
    id: int
    farm_id: int
    tag_number: str
    breed: str
    gender: CowGender
    health_status: HealthStatus
    pregnancy_status: PregnancyStatus
    photo_path: Optional[str]
    age_years: Optional[float]
    is_active: bool


@dataclass(frozen=True)
class CowDetail(CowSummary):
    rfid_number: Optional[str]
    qr_code_value: str
    qr_code_path: Optional[str]
    birth_date: Optional[date]
    weight_kg: Optional[float]
    height_cm: Optional[float]
    color: Optional[str]
    horn_type: Optional[HornType]
    expected_delivery_date: Optional[date]
    calving_date: Optional[date]
    purchase_date: Optional[date]
    purchase_price: Optional[float]
    location: Optional[str]
    notes: Optional[str]


class CowController(BaseController):
    def list_cows(self, actor: AuthenticatedUser, farm_id: int) -> List[CowSummary]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = get_farm_or_raise(farm_service, farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            cows = CowService(session).list_for_farm(farm_id)
            return [self._to_summary(cow) for cow in cows]

    def get_cow(self, actor: AuthenticatedUser, cow_id: int) -> CowDetail:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            return self._to_detail(cow)

    def create_cow(
        self,
        actor: AuthenticatedUser,
        *,
        farm_id: int,
        tag_number: str,
        breed: str,
        gender: CowGender,
        birth_date: Optional[date] = None,
        rfid_number: Optional[str] = None,
        weight_kg: Optional[float] = None,
        height_cm: Optional[float] = None,
        color: Optional[str] = None,
        horn_type: Optional[HornType] = None,
        pregnancy_status: PregnancyStatus = PregnancyStatus.OPEN,
        expected_delivery_date: Optional[date] = None,
        calving_date: Optional[date] = None,
        health_status: HealthStatus = HealthStatus.HEALTHY,
        purchase_date: Optional[date] = None,
        purchase_price: Optional[float] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
        photo_source_path: Optional[Path] = None,
    ) -> CowDetail:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            farm = get_farm_or_raise(farm_service, farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_COWS)

            self._validate_cow_fields(tag_number, breed, weight_kg, height_cm, purchase_price)
            if cow_service.tag_number_exists(farm_id, tag_number):
                raise CowError(f"Tag number '{tag_number}' is already used on this farm.")
            if rfid_number and cow_service.rfid_exists(rfid_number):
                raise CowError("That RFID number is already registered to another cow.")

            photo_path = None
            if photo_source_path is not None:
                photo_path = save_image(photo_source_path, subdir="cows", prefix="cow")

            qr_value = generate_qr_value()
            qr_path = generate_qr_image(qr_value, subdir="qr_codes", prefix="cow")

            cow = cow_service.create(
                farm_id=farm_id,
                tag_number=tag_number.strip(),
                rfid_number=(rfid_number.strip() or None) if rfid_number else None,
                breed=breed.strip(),
                gender=gender,
                birth_date=birth_date,
                weight_kg=weight_kg,
                height_cm=height_cm,
                color=(color.strip() or None) if color else None,
                horn_type=horn_type,
                pregnancy_status=pregnancy_status,
                expected_delivery_date=expected_delivery_date,
                calving_date=calving_date,
                health_status=health_status,
                purchase_date=purchase_date,
                purchase_price=purchase_price,
                location=(location.strip() or None) if location else None,
                notes=(notes.strip() or None) if notes else None,
                photo_path=photo_path,
                qr_code_value=qr_value,
                qr_code_path=qr_path,
            )
            self.logger.info("Cow registered: %s (farm_id=%s)", cow.tag_number, farm_id)
            return self._to_detail(cow)

    def update_cow(
        self,
        actor: AuthenticatedUser,
        cow_id: int,
        *,
        tag_number: str,
        breed: str,
        gender: CowGender,
        birth_date: Optional[date] = None,
        rfid_number: Optional[str] = None,
        weight_kg: Optional[float] = None,
        height_cm: Optional[float] = None,
        color: Optional[str] = None,
        horn_type: Optional[HornType] = None,
        pregnancy_status: PregnancyStatus = PregnancyStatus.OPEN,
        expected_delivery_date: Optional[date] = None,
        calving_date: Optional[date] = None,
        health_status: HealthStatus = HealthStatus.HEALTHY,
        purchase_date: Optional[date] = None,
        purchase_price: Optional[float] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
        photo_source_path: Optional[Path] = None,
        remove_photo: bool = False,
    ) -> CowDetail:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            cow = get_cow_or_raise(cow_service, cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_COWS)

            self._validate_cow_fields(tag_number, breed, weight_kg, height_cm, purchase_price)
            if cow_service.tag_number_exists(cow.farm_id, tag_number, exclude_cow_id=cow_id):
                raise CowError(f"Tag number '{tag_number}' is already used on this farm.")
            if rfid_number and cow_service.rfid_exists(rfid_number, exclude_cow_id=cow_id):
                raise CowError("That RFID number is already registered to another cow.")

            new_photo_path = cow.photo_path
            if photo_source_path is not None:
                delete_image(cow.photo_path)
                new_photo_path = save_image(photo_source_path, subdir="cows", prefix="cow")
            elif remove_photo:
                delete_image(cow.photo_path)
                new_photo_path = None

            cow_service.update(
                cow_id,
                tag_number=tag_number.strip(),
                rfid_number=(rfid_number.strip() or None) if rfid_number else None,
                breed=breed.strip(),
                gender=gender,
                birth_date=birth_date,
                weight_kg=weight_kg,
                height_cm=height_cm,
                color=(color.strip() or None) if color else None,
                horn_type=horn_type,
                pregnancy_status=pregnancy_status,
                expected_delivery_date=expected_delivery_date,
                calving_date=calving_date,
                health_status=health_status,
                purchase_date=purchase_date,
                purchase_price=purchase_price,
                location=(location.strip() or None) if location else None,
                notes=(notes.strip() or None) if notes else None,
                photo_path=new_photo_path,
            )
            self.logger.info("Cow updated: %s", cow.tag_number)
            return self._to_detail(cow)

    def delete_cow(self, actor: AuthenticatedUser, cow_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow_service = CowService(session)
            cow = get_cow_or_raise(cow_service, cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_COWS)
            cow_service.delete(cow_id)
            self.logger.info("Cow deactivated: %s", cow.tag_number)

    # ---- Validation ---------------------------------------------------------

    @staticmethod
    def _validate_cow_fields(
        tag_number: str,
        breed: str,
        weight_kg: Optional[float],
        height_cm: Optional[float],
        purchase_price: Optional[float],
    ) -> None:
        if not tag_number or not tag_number.strip():
            raise CowError("Tag number is required.")
        if not breed or not breed.strip():
            raise CowError("Breed is required.")
        if weight_kg is not None and not validate_non_negative(weight_kg):
            raise CowError("Weight cannot be negative.")
        if height_cm is not None and not validate_non_negative(height_cm):
            raise CowError("Height cannot be negative.")
        if purchase_price is not None and not validate_non_negative(purchase_price):
            raise CowError("Purchase price cannot be negative.")

    # ---- Mapping ------------------------------------------------------------

    @staticmethod
    def _compute_age_years(birth_date: Optional[date]) -> Optional[float]:
        if birth_date is None:
            return None
        return round((date.today() - birth_date).days / 365.25, 1)

    @classmethod
    def _to_summary(cls, cow: Cow) -> CowSummary:
        return CowSummary(
            id=cow.id,
            farm_id=cow.farm_id,
            tag_number=cow.tag_number,
            breed=cow.breed,
            gender=cow.gender,
            health_status=cow.health_status,
            pregnancy_status=cow.pregnancy_status,
            photo_path=cow.photo_path,
            age_years=cls._compute_age_years(cow.birth_date),
            is_active=cow.is_active,
        )

    @classmethod
    def _to_detail(cls, cow: Cow) -> CowDetail:
        summary = cls._to_summary(cow)
        return CowDetail(
            **asdict(summary),
            rfid_number=cow.rfid_number,
            qr_code_value=cow.qr_code_value,
            qr_code_path=cow.qr_code_path,
            birth_date=cow.birth_date,
            weight_kg=cow.weight_kg,
            height_cm=cow.height_cm,
            color=cow.color,
            horn_type=cow.horn_type,
            expected_delivery_date=cow.expected_delivery_date,
            calving_date=cow.calving_date,
            purchase_date=cow.purchase_date,
            purchase_price=cow.purchase_price,
            location=cow.location,
            notes=cow.notes,
        )
