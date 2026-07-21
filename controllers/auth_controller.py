"""Authentication and account-management orchestration.

Views depend only on `AuthController` and `AuthenticatedUser` — never on
`User` (the ORM entity) or a database session — so the login/session state
held by the UI can never trigger a lazy-load against a closed session.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from controllers.base_controller import BaseController
from database.session import get_db_session
from models.user import User, UserRole
from services.user_service import UserService
from utils.exceptions import AppError
from utils.permissions import Permission, has_permission
from utils.security import hash_password, normalize_answer, validate_password_strength, verify_password
from utils.validators import validate_email, validate_username


class AuthenticationError(AppError):
    """Raised for any login/setup/reset/registration failure the UI should surface."""


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    full_name: str
    email: str
    role: UserRole
    is_active: bool


class AuthController(BaseController):
    def has_any_users(self) -> bool:
        with get_db_session() as session:
            return UserService(session).any_users_exist()

    def create_initial_admin(
        self,
        *,
        username: str,
        email: str,
        full_name: str,
        password: str,
        security_question: str,
        security_answer: str,
    ) -> AuthenticatedUser:
        """First-run setup: only allowed while the users table is empty."""
        with get_db_session() as session:
            service = UserService(session)
            if service.any_users_exist():
                raise AuthenticationError("Setup has already been completed.")
            self._validate_new_account_fields(
                username, email, full_name, password, security_question, security_answer, service
            )
            user = service.create(
                username=username.strip(),
                email=email.strip().lower(),
                full_name=full_name.strip(),
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                security_question=security_question.strip(),
                security_answer_hash=hash_password(normalize_answer(security_answer)),
                last_login_at=datetime.now(timezone.utc),
            )
            self.logger.info("Initial admin account created: %s", user.username)
            return self._to_authenticated_user(user)

    def register_user(
        self,
        *,
        actor_role: UserRole,
        username: str,
        email: str,
        full_name: str,
        password: str,
        role: UserRole,
        security_question: str,
        security_answer: str,
    ) -> AuthenticatedUser:
        if not has_permission(actor_role, Permission.MANAGE_USERS):
            raise AuthenticationError("You do not have permission to create user accounts.")
        with get_db_session() as session:
            service = UserService(session)
            self._validate_new_account_fields(
                username, email, full_name, password, security_question, security_answer, service
            )
            user = service.create(
                username=username.strip(),
                email=email.strip().lower(),
                full_name=full_name.strip(),
                password_hash=hash_password(password),
                role=role,
                security_question=security_question.strip(),
                security_answer_hash=hash_password(normalize_answer(security_answer)),
            )
            self.logger.info("User account created: %s (%s)", user.username, role.value)
            return self._to_authenticated_user(user)

    def login(self, username: str, password: str) -> AuthenticatedUser:
        if not username.strip() or not password:
            raise AuthenticationError("Username and password are required.")
        with get_db_session() as session:
            user = UserService(session).get_by_username(username)
            if user is None or not user.is_active or not verify_password(password, user.password_hash):
                self.logger.warning("Failed login attempt for username=%s", username)
                raise AuthenticationError("Invalid username or password.")
            user.last_login_at = datetime.now(timezone.utc)
            session.flush()
            self.logger.info("User logged in: %s", user.username)
            return self._to_authenticated_user(user)

    def get_security_question(self, username: str) -> str:
        with get_db_session() as session:
            user = UserService(session).get_by_username(username)
            if user is None or not user.is_active:
                raise AuthenticationError("No active account found with that username.")
            return user.security_question

    def reset_password(self, *, username: str, security_answer: str, new_password: str) -> None:
        with get_db_session() as session:
            user = UserService(session).get_by_username(username)
            if user is None or not user.is_active:
                raise AuthenticationError("No active account found with that username.")
            if not verify_password(normalize_answer(security_answer), user.security_answer_hash):
                self.logger.warning("Failed security-answer attempt for username=%s", username)
                raise AuthenticationError("Security answer is incorrect.")
            is_valid, message = validate_password_strength(new_password)
            if not is_valid:
                raise AuthenticationError(message)
            user.password_hash = hash_password(new_password)
            session.flush()
            self.logger.info("Password reset for user: %s", user.username)

    def list_users(self) -> List[AuthenticatedUser]:
        with get_db_session() as session:
            return [self._to_authenticated_user(u) for u in UserService(session).get_all(include_inactive=True)]

    def set_user_active(self, *, actor_role: UserRole, user_id: int, is_active: bool) -> None:
        if not has_permission(actor_role, Permission.MANAGE_USERS):
            raise AuthenticationError("You do not have permission to manage user accounts.")
        with get_db_session() as session:
            service = UserService(session)
            user = service.get_by_id(user_id)
            if user is None:
                raise AuthenticationError("User not found.")
            user.is_active = is_active
            session.flush()

    @staticmethod
    def _validate_new_account_fields(
        username: str,
        email: str,
        full_name: str,
        password: str,
        security_question: str,
        security_answer: str,
        service: UserService,
    ) -> None:
        if not validate_username(username):
            raise AuthenticationError(
                "Username must be 3-50 characters (letters, numbers, '.', '_' only)."
            )
        if not validate_email(email):
            raise AuthenticationError("Enter a valid email address.")
        if not full_name.strip():
            raise AuthenticationError("Full name is required.")
        if not security_question.strip() or not security_answer.strip():
            raise AuthenticationError("A security question and answer are required for password recovery.")
        is_valid, message = validate_password_strength(password)
        if not is_valid:
            raise AuthenticationError(message)
        if service.username_exists(username):
            raise AuthenticationError("That username is already taken.")
        if service.email_exists(email):
            raise AuthenticationError("That email is already registered.")

    @staticmethod
    def _to_authenticated_user(user: User) -> AuthenticatedUser:
        return AuthenticatedUser(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
        )
