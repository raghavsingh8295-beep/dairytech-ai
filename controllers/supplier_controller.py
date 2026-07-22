"""Supplier orchestration: farm-scoped visibility/permissions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.farm_access import ensure_can_access_farm, get_farm_or_raise
from database.session import get_db_session
from models.inventory import Supplier
from services.farm_service import FarmService
from services.supplier_service import SupplierService
from utils.exceptions import AppError
from utils.permissions import Permission


class SupplierError(AppError):
    """Raised for any supplier-record failure the UI should surface."""


@dataclass(frozen=True)
class SupplierEntry:
    id: int
    farm_id: int
    name: str
    contact_phone: Optional[str]
    contact_email: Optional[str]
    address: Optional[str]
    notes: Optional[str]
    is_active: bool


class SupplierController(BaseController):
    def list_for_farm(self, actor: AuthenticatedUser, farm_id: int) -> List[SupplierEntry]:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = get_farm_or_raise(farm_service, farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            records = SupplierService(session).list_for_farm(farm_id)
            return [self._to_entry(r) for r in records]

    def create_supplier(
        self,
        actor: AuthenticatedUser,
        *,
        farm_id: int,
        name: str,
        contact_phone: Optional[str] = None,
        contact_email: Optional[str] = None,
        address: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> SupplierEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = get_farm_or_raise(farm_service, farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_INVENTORY)

            if not name.strip():
                raise SupplierError("Supplier name is required.")
            record = SupplierService(session).create(
                farm_id=farm_id,
                name=name.strip(),
                contact_phone=(contact_phone.strip() or None) if contact_phone else None,
                contact_email=(contact_email.strip() or None) if contact_email else None,
                address=(address.strip() or None) if address else None,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Supplier created: farm_id=%s name=%s", farm_id, record.name)
            return self._to_entry(record)

    def update_supplier(
        self,
        actor: AuthenticatedUser,
        supplier_id: int,
        *,
        name: str,
        contact_phone: Optional[str] = None,
        contact_email: Optional[str] = None,
        address: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> SupplierEntry:
        with get_db_session() as session:
            farm_service = FarmService(session)
            supplier_service = SupplierService(session)
            record = supplier_service.get_by_id(supplier_id)
            if record is None:
                raise SupplierError("Supplier not found.")
            farm = get_farm_or_raise(farm_service, record.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_INVENTORY)

            if not name.strip():
                raise SupplierError("Supplier name is required.")
            supplier_service.update(
                supplier_id,
                name=name.strip(),
                contact_phone=(contact_phone.strip() or None) if contact_phone else None,
                contact_email=(contact_email.strip() or None) if contact_email else None,
                address=(address.strip() or None) if address else None,
                notes=(notes.strip() or None) if notes else None,
            )
            self.logger.info("Supplier updated: id=%s", supplier_id)
            return self._to_entry(record)

    def delete_supplier(self, actor: AuthenticatedUser, supplier_id: int) -> None:
        with get_db_session() as session:
            farm_service = FarmService(session)
            supplier_service = SupplierService(session)
            record = supplier_service.get_by_id(supplier_id)
            if record is None:
                raise SupplierError("Supplier not found.")
            farm = get_farm_or_raise(farm_service, record.farm_id)
            ensure_can_access_farm(farm_service, actor, farm, required_permission=Permission.MANAGE_INVENTORY)
            supplier_service.delete(supplier_id)
            self.logger.info("Supplier deactivated: id=%s", supplier_id)

    @staticmethod
    def _to_entry(record: Supplier) -> SupplierEntry:
        return SupplierEntry(
            id=record.id,
            farm_id=record.farm_id,
            name=record.name,
            contact_phone=record.contact_phone,
            contact_email=record.contact_email,
            address=record.address,
            notes=record.notes,
            is_active=record.is_active,
        )
