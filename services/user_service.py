from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select

from models.user import User, UserRole
from services.base_service import BaseService


class UserService(BaseService[User]):
    model = User

    def list_by_role(self, role: UserRole, *, only_active: bool = True) -> List[User]:
        stmt = select(User).where(User.role == role)
        if only_active:
            stmt = stmt.where(User.is_active.is_(True))
        return list(self.session.execute(stmt).scalars().all())

    def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(func.lower(User.username) == username.strip().lower())
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(func.lower(User.email) == email.strip().lower())
        return self.session.execute(stmt).scalar_one_or_none()

    def username_exists(self, username: str) -> bool:
        return self.get_by_username(username) is not None

    def email_exists(self, email: str) -> bool:
        return self.get_by_email(email) is not None

    def any_users_exist(self) -> bool:
        stmt = select(func.count()).select_from(User)
        return self.session.execute(stmt).scalar_one() > 0
