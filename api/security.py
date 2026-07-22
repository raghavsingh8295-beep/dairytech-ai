"""JWT issuance and the FastAPI dependency that reconstructs an
AuthenticatedUser from a bearer token.

This is the whole trick that lets the API reuse every desktop controller
unmodified: every controller method already takes `actor: AuthenticatedUser`
as its first argument, built for the desktop app's in-memory session. A
decoded JWT reconstructs that exact same dataclass, so
`FarmController().list_farms(actor)` behaves identically whether `actor`
came from a CustomTkinter session or an HTTP request.

Known simplification: the token embeds a snapshot of role/is_active at
login time and is trusted for up to JWT_EXPIRY_DAYS. If an Admin
deactivates a user or changes their role mid-token-lifetime, that user's
existing token keeps the old permissions until it expires or they log in
again — there's no per-request DB re-check. Fine for local testing; a
production deployment would want either much shorter-lived tokens with
refresh, or a per-request active-user check.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import settings
from controllers.auth_controller import AuthenticatedUser
from models.user import UserRole

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
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please log in again."
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token."
        ) from exc

    return AuthenticatedUser(
        id=int(payload["sub"]),
        username=payload["username"],
        full_name=payload["full_name"],
        email=payload["email"],
        role=UserRole(payload["role"]),
        is_active=payload["is_active"],
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    return _decode_token(credentials.credentials)
