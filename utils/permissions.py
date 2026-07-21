"""Role-based access control.

Every feature module gates its write actions through `has_permission`
rather than checking `role == UserRole.ADMIN` inline, so permission rules
stay in one place as new modules (and possibly new roles) are added.
"""
from __future__ import annotations

import enum
from typing import Dict, FrozenSet

from models.user import UserRole


class Permission(str, enum.Enum):
    MANAGE_USERS = "manage_users"  # create/deactivate accounts, assign roles
    MANAGE_FARMS = "manage_farms"
    MANAGE_COWS = "manage_cows"
    RECORD_DAILY_DATA = "record_daily_data"
    MANAGE_HEALTH = "manage_health"
    MANAGE_BREEDING = "manage_breeding"
    MANAGE_INVENTORY = "manage_inventory"
    MANAGE_FINANCE = "manage_finance"
    VIEW_REPORTS = "view_reports"


ROLE_PERMISSIONS: Dict[UserRole, FrozenSet[Permission]] = {
    UserRole.ADMIN: frozenset(Permission),
    UserRole.FARM_OWNER: frozenset(
        {
            Permission.MANAGE_FARMS,
            Permission.MANAGE_COWS,
            Permission.RECORD_DAILY_DATA,
            Permission.MANAGE_HEALTH,
            Permission.MANAGE_BREEDING,
            Permission.MANAGE_INVENTORY,
            Permission.MANAGE_FINANCE,
            Permission.VIEW_REPORTS,
        }
    ),
    UserRole.EMPLOYEE: frozenset(
        {
            Permission.RECORD_DAILY_DATA,
            Permission.MANAGE_HEALTH,
            Permission.VIEW_REPORTS,
        }
    ),
}


def has_permission(role: UserRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
