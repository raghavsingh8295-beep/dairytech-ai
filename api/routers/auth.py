"""Authentication endpoints. No business logic here — just translates
HTTP <-> the existing AuthController."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas import LoginRequest, LoginResponse, UserOut
from api.security import create_access_token, get_current_user
from controllers.auth_controller import AuthController, AuthenticatedUser, AuthenticationError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    try:
        user = AuthController().login(payload.username, payload.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    token = create_access_token(user)
    return LoginResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: AuthenticatedUser = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
