"""Farm management orchestration: visibility scoping, ownership checks,
photo handling. Views depend only on the dataclasses below, never on the
`Farm` ORM entity.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from database.session import get_db_session
from models.farm import Farm
from models.user import UserRole
from services.farm_service import FarmService
from services.user_service import UserService
from utils.exceptions import AppError
from utils.file_storage import delete_image, save_image
from utils.permissions import Permission, has_permission
from utils.validators import validate_latitude, validate_longitude


class FarmError(AppError):
    """Raised for any farm-related failure the UI should surface."""


@dataclass(frozen=True)
class UserOption:
    """A user shown in an owner/employee picker dropdown."""

    id: int
    username: str
    full_name: str


@dataclass(frozen=True)
class FarmSummary:
    id: int
    name: str
    owner_id: int
    owner_name: str
    phone_number: Optional[str]
    address: Optional[str]
    photo_path: Optional[str]
    employee_count: int
    is_active: bool


@dataclass(frozen=True)
class FarmDetail(FarmSummary):
    gps_latitude: Optional[float]
    gps_longitude: Optional[float]
    notes: Optional[str]


class FarmController(BaseController):
    def list_farms(self, actor: AuthenticatedUser) -> List[FarmSummary]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            if actor.role == UserRole.ADMIN:
                farms = farm_service.get_all()
            elif actor.role == UserRole.FARM_OWNER:
                farms = farm_service.list_owned_by(actor.id)
            else:
                farms = farm_service.list_for_employee(actor.id)
            return [self._to_summary(farm_service, farm) for farm in farms]

    def get_farm(self, actor: AuthenticatedUser, farm_id: int) -> FarmDetail:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = self._require_farm(farm_service, farm_id)
            self._ensure_can_view(farm_service, actor, farm)
            return self._to_detail(farm_service, farm)

    def create_farm(
        self,
        actor: AuthenticatedUser,
        *,
        name: str,
        owner_id: Optional[int] = None,
        phone_number: Optional[str] = None,
        address: Optional[str] = None,
        gps_latitude: Optional[float] = None,
        gps_longitude: Optional[float] = None,
        photo_source_path: Optional[Path] = None,
        notes: Optional[str] = None,
    ) -> FarmDetail:
        if not has_permission(actor.role, Permission.MANAGE_FARMS):
            raise FarmError("You do not have permission to create farms.")
        with get_db_session() as session:
            user_service = UserService(session)
            farm_service = FarmService(session)

            resolved_owner_id = self._resolve_owner_id(actor, owner_id, user_service)
            self._validate_farm_fields(name, gps_latitude, gps_longitude)

            photo_path = None
            if photo_source_path is not None:
                photo_path = save_image(photo_source_path, subdir="farms", prefix="farm")

            farm = farm_service.create(
                name=name.strip(),
                owner_id=resolved_owner_id,
                phone_number=(phone_number.strip() or None) if phone_number else None,
                address=(address.strip() or None) if address else None,
                gps_latitude=gps_latitude,
                gps_longitude=gps_longitude,
                photo_path=photo_path,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Farm created: %s (owner_id=%s)", farm.name, resolved_owner_id)
            return self._to_detail(farm_service, farm)

    def update_farm(
        self,
        actor: AuthenticatedUser,
        farm_id: int,
        *,
        name: str,
        phone_number: Optional[str] = None,
        address: Optional[str] = None,
        gps_latitude: Optional[float] = None,
        gps_longitude: Optional[float] = None,
        notes: Optional[str] = None,
        photo_source_path: Optional[Path] = None,
        remove_photo: bool = False,
    ) -> FarmDetail:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = self._require_farm(farm_service, farm_id)
            self._ensure_can_manage(actor, farm)
            self._validate_farm_fields(name, gps_latitude, gps_longitude)

            new_photo_path = farm.photo_path
            if photo_source_path is not None:
                delete_image(farm.photo_path)
                new_photo_path = save_image(photo_source_path, subdir="farms", prefix="farm")
            elif remove_photo:
                delete_image(farm.photo_path)
                new_photo_path = None

            farm_service.update(
                farm_id,
                name=name.strip(),
                phone_number=(phone_number.strip() or None) if phone_number else None,
                address=(address.strip() or None) if address else None,
                gps_latitude=gps_latitude,
                gps_longitude=gps_longitude,
                notes=(notes.strip() or None) if notes else None,
                photo_path=new_photo_path,
            )
            self.logger.info("Farm updated: %s", farm.name)
            return self._to_detail(farm_service, farm)

    def delete_farm(self, actor: AuthenticatedUser, farm_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = self._require_farm(farm_service, farm_id)
            self._ensure_can_manage(actor, farm)
            farm_service.delete(farm_id)
            self.logger.info("Farm deactivated: %s", farm.name)

    def assign_employee(self, actor: AuthenticatedUser, *, farm_id: int, user_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = self._require_farm(farm_service, farm_id)
            self._ensure_can_manage(actor, farm)

            user = UserService(session).get_by_id(user_id)
            if user is None or user.role != UserRole.EMPLOYEE or not user.is_active:
                raise FarmError("Select an active employee account.")
            if farm_service.is_employee_assigned(farm_id, user_id):
                raise FarmError("This employee is already assigned to the farm.")
            farm_service.assign_employee(farm_id, user_id)
            self.logger.info("Employee %s assigned to farm %s", user.username, farm.name)

    def remove_employee(self, actor: AuthenticatedUser, *, farm_id: int, user_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = self._require_farm(farm_service, farm_id)
            self._ensure_can_manage(actor, farm)
            if not farm_service.remove_employee(farm_id, user_id):
                raise FarmError("That employee is not assigned to this farm.")

    def list_employees(self, actor: AuthenticatedUser, farm_id: int) -> List[UserOption]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = self._require_farm(farm_service, farm_id)
            self._ensure_can_view(farm_service, actor, farm)
            return [self._to_option(u) for u in farm_service.list_employees(farm_id)]

    def list_assignable_employees(self, actor: AuthenticatedUser, farm_id: int) -> List[UserOption]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = self._require_farm(farm_service, farm_id)
            self._ensure_can_manage(actor, farm)
            assigned_ids = {u.id for u in farm_service.list_employees(farm_id)}
            candidates = UserService(session).list_by_role(UserRole.EMPLOYEE)
            return [self._to_option(u) for u in candidates if u.id not in assigned_ids]

    def list_farm_owner_options(self, actor: AuthenticatedUser) -> List[UserOption]:
        if actor.role != UserRole.ADMIN:
            return []
        with get_db_session() as session:
            owners = UserService(session).list_by_role(UserRole.FARM_OWNER)
            return [self._to_option(u) for u in owners]

    # ---- Access control ---------------------------------------------------

    @staticmethod
    def _ensure_can_view(farm_service: FarmService, actor: AuthenticatedUser, farm: Farm) -> None:
        if actor.role == UserRole.ADMIN:
            return
        if actor.role == UserRole.FARM_OWNER and farm.owner_id == actor.id:
            return
        if actor.role == UserRole.EMPLOYEE and farm_service.is_employee_assigned(farm.id, actor.id):
            return
        raise FarmError("You do not have access to this farm.")

    @staticmethod
    def _ensure_can_manage(actor: AuthenticatedUser, farm: Farm) -> None:
        if not has_permission(actor.role, Permission.MANAGE_FARMS):
            raise FarmError("You do not have permission to manage farms.")
        if actor.role == UserRole.FARM_OWNER and farm.owner_id != actor.id:
            raise FarmError("You can only manage farms you own.")

    @staticmethod
    def _resolve_owner_id(
        actor: AuthenticatedUser, owner_id: Optional[int], user_service: UserService
    ) -> int:
        if actor.role == UserRole.FARM_OWNER:
            return actor.id
        if owner_id is None:
            raise FarmError("Select a farm owner.")
        owner = user_service.get_by_id(owner_id)
        if owner is None or owner.role != UserRole.FARM_OWNER or not owner.is_active:
            raise FarmError("Select a valid, active Farm Owner account.")
        return owner_id

    @staticmethod
    def _validate_farm_fields(name: str, latitude: Optional[float], longitude: Optional[float]) -> None:
        if not name or not name.strip():
            raise FarmError("Farm name is required.")
        if latitude is not None and not validate_latitude(latitude):
            raise FarmError("Latitude must be between -90 and 90.")
        if longitude is not None and not validate_longitude(longitude):
            raise FarmError("Longitude must be between -180 and 180.")

    @staticmethod
    def _require_farm(farm_service: FarmService, farm_id: int) -> Farm:
        farm = farm_service.get_by_id(farm_id)
        if farm is None:
            raise FarmError("Farm not found.")
        return farm

    # ---- Mapping ------------------------------------------------------------

    @staticmethod
    def _to_option(user) -> UserOption:
        return UserOption(id=user.id, username=user.username, full_name=user.full_name)

    @staticmethod
    def _to_summary(farm_service: FarmService, farm: Farm) -> FarmSummary:
        return FarmSummary(
            id=farm.id,
            name=farm.name,
            owner_id=farm.owner_id,
            owner_name=farm.owner.full_name,
            phone_number=farm.phone_number,
            address=farm.address,
            photo_path=farm.photo_path,
            employee_count=farm_service.count_employees(farm.id),
            is_active=farm.is_active,
        )

    @classmethod
    def _to_detail(cls, farm_service: FarmService, farm: Farm) -> FarmDetail:
        summary = cls._to_summary(farm_service, farm)
        return FarmDetail(
            **asdict(summary),
            gps_latitude=farm.gps_latitude,
            gps_longitude=farm.gps_longitude,
            notes=farm.notes,
        )
