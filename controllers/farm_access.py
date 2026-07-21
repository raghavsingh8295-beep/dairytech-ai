"""Shared farm-level access control and lookup, used by every controller
whose records belong to a farm (Farm itself, Cow, and later Health,
Breeding, Inventory, Finance, Daily Recording).
"""
from __future__ import annotations

from typing import Optional

from controllers.auth_controller import AuthenticatedUser
from models.farm import Farm
from models.user import UserRole
from services.farm_service import FarmService
from utils.exceptions import AppError
from utils.permissions import Permission, has_permission


class FarmAccessError(AppError):
    """Raised when the actor cannot view/manage a farm or a farm-scoped record."""


def get_farm_or_raise(farm_service: FarmService, farm_id: int) -> Farm:
    farm = farm_service.get_by_id(farm_id)
    if farm is None:
        raise FarmAccessError("Farm not found.")
    return farm


def ensure_can_access_farm(
    farm_service: FarmService,
    actor: AuthenticatedUser,
    farm: Farm,
    *,
    required_permission: Optional[Permission] = None,
) -> None:
    """Raise FarmAccessError unless `actor` can see (and, if given, act on) `farm`.

    Visibility: Admin sees everything; a Farm Owner sees farms they own; an
    Employee sees only farms they're assigned to. When `required_permission`
    is given, the actor must additionally hold that permission — used for
    write actions (creating a cow, editing farm details, ...).
    """
    if actor.role == UserRole.ADMIN:
        pass
    elif actor.role == UserRole.FARM_OWNER:
        if farm.owner_id != actor.id:
            raise FarmAccessError("You do not have access to this farm.")
    elif actor.role == UserRole.EMPLOYEE:
        if not farm_service.is_employee_assigned(farm.id, actor.id):
            raise FarmAccessError("You do not have access to this farm.")
    else:
        raise FarmAccessError("You do not have access to this farm.")

    if required_permission is not None and not has_permission(actor.role, required_permission):
        raise FarmAccessError("You do not have permission to perform this action.")
