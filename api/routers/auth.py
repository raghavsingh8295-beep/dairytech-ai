"""Authentication endpoints. No business logic here — just translates
HTTP <-> the existing AuthController."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas import LoginRequest, LoginResponse, SignUpIn, UserOut
from api.security import create_access_token, get_current_user
from controllers.auth_controller import AuthController, AuthenticatedUser, AuthenticationError
from utils.exceptions import AppError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    try:
        user = AuthController().login(payload.username, payload.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    token = create_access_token(user)
    return LoginResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/signup", response_model=LoginResponse)
def signup(payload: SignUpIn) -> LoginResponse:
    """Public — no auth required. Creates a new Farm Owner account and logs
    them straight in, same response shape as /login, so the app can treat
    signup and login as interchangeable entry points."""
    try:
        user = AuthController().sign_up(**payload.model_dump())
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    token = create_access_token(user)
    return LoginResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: AuthenticatedUser = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
