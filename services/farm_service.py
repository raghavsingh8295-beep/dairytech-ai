from __future__ import annotations

from typing import List

from sqlalchemy import func, select

from models.farm import Farm, FarmEmployee
from models.user import User
from services.base_service import BaseService


class FarmService(BaseService[Farm]):
    model = Farm

    def list_owned_by(self, owner_id: int) -> List[Farm]:
        stmt = select(Farm).where(Farm.owner_id == owner_id, Farm.is_active.is_(True))
        return list(self.session.execute(stmt).scalars().all())

    def list_for_employee(self, user_id: int) -> List[Farm]:
        stmt = (
            select(Farm)
            .join(FarmEmployee, FarmEmployee.farm_id == Farm.id)
            .where(FarmEmployee.user_id == user_id, Farm.is_active.is_(True))
        )
        return list(self.session.execute(stmt).scalars().all())

    def count_employees(self, farm_id: int) -> int:
        stmt = select(func.count()).select_from(FarmEmployee).where(FarmEmployee.farm_id == farm_id)
        return self.session.execute(stmt).scalar_one()

    def list_employees(self, farm_id: int) -> List[User]:
        stmt = (
            select(User)
            .join(FarmEmployee, FarmEmployee.user_id == User.id)
            .where(FarmEmployee.farm_id == farm_id)
        )
        return list(self.session.execute(stmt).scalars().all())

    def is_employee_assigned(self, farm_id: int, user_id: int) -> bool:
        stmt = select(FarmEmployee).where(FarmEmployee.farm_id == farm_id, FarmEmployee.user_id == user_id)
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def assign_employee(self, farm_id: int, user_id: int) -> FarmEmployee:
        link = FarmEmployee(farm_id=farm_id, user_id=user_id)
        self.session.add(link)
        self.session.flush()
        return link

    def remove_employee(self, farm_id: int, user_id: int) -> bool:
        stmt = select(FarmEmployee).where(FarmEmployee.farm_id == farm_id, FarmEmployee.user_id == user_id)
        link = self.session.execute(stmt).scalar_one_or_none()
        if link is None:
            return False
        self.session.delete(link)
        self.session.flush()
        return True
