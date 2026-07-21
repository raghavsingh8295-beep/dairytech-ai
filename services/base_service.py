"""Generic CRUD repository that every feature service inherits from.

Concrete services (FarmService, CowService, ...) set `model` to their
SQLAlchemy model and get create/read/update/delete for free, plus a place
to add entity-specific query methods. Business logic that spans multiple
services belongs in controllers, not here.
"""
from __future__ import annotations

from typing import Any, Generic, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.base import Base
from utils.logger import get_logger

ModelType = TypeVar("ModelType", bound=Base)

logger = get_logger(__name__)


class BaseService(Generic[ModelType]):
    model: Type[ModelType]

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, **fields: Any) -> ModelType:
        instance = self.model(**fields)
        self.session.add(instance)
        self.session.flush()
        return instance

    def get_by_id(self, record_id: int) -> Optional[ModelType]:
        return self.session.get(self.model, record_id)

    def get_all(self, *, include_inactive: bool = False) -> List[ModelType]:
        stmt = select(self.model)
        if not include_inactive and hasattr(self.model, "is_active"):
            stmt = stmt.where(self.model.is_active.is_(True))
        return list(self.session.execute(stmt).scalars().all())

    def update(self, record_id: int, **fields: Any) -> Optional[ModelType]:
        instance = self.get_by_id(record_id)
        if instance is None:
            return None
        for key, value in fields.items():
            setattr(instance, key, value)
        self.session.flush()
        return instance

    def delete(self, record_id: int) -> bool:
        """Soft-delete if the model supports it, otherwise remove the row."""
        instance = self.get_by_id(record_id)
        if instance is None:
            return False
        if hasattr(instance, "is_active"):
            instance.is_active = False
        else:
            self.session.delete(instance)
        self.session.flush()
        return True
