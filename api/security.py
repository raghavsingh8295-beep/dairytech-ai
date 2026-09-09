"""JWT issuance and the FastAPI dependency that reconstructs an
AuthenticatedUser from a bearer token.

This is the whole trick that lets the API reuse every desktop controller
unmodified: every controller method already takes `actor: AuthenticatedUser`
as its first argument, built for the desktop app's in-memory session. A
decoded JWT reconstructs that exact same dataclass, so
`FarmController().list_farms(actor)` behaves identically whether `actor`
came from a CustomTkinter session or an HTTP request.

Every authenticated request reloads the account from the database so account
removal, deactivation, and role changes take effect on the next request.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import settings
from controllers.auth_controller import AuthenticatedUser
from database.session import get_db_session
from services.user_service import UserService

_bearer_scheme = HTTPBearer()


def create_access_token(user: AuthenticatedUser) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str) -> AuthenticatedUser:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
        user_id = int(payload["sub"])
        if user_id <= 0:
            raise ValueError("Invalid user ID")
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please log in again."
        ) from exc
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token."
        ) from exc

    with get_db_session() as session:
        user = UserService(session).get_by_id(user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account unavailable. Please log in again.",
            )
        return AuthenticatedUser(
            id=user.id, username=user.username, full_name=user.full_name,
            email=user.email, role=user.role, is_active=user.is_active,
        )



def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    return _decode_token(credentials.credentials)
