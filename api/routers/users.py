"""User account endpoints. Mirrors AuthController exactly — only Admins
(and anyone else granted MANAGE_USERS) can list/create/edit/deactivate
accounts, enforced in the controller, identically to the desktop app."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas import UserCreateIn, UserOut, UserUpdateIn
from api.security import get_current_user
from controllers.auth_controller import AuthController, AuthenticatedUser
from utils.exceptions import AppError

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=List[UserOut])
def list_users(current_user: AuthenticatedUser = Depends(get_current_user)) -> List[UserOut]:
    if current_user.role.value != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    users = AuthController().list_users()
    return [UserOut.model_validate(u) for u in users]


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreateIn, current_user: AuthenticatedUser = Depends(get_current_user)
) -> UserOut:
    try:
        user = AuthController().register_user(actor_role=current_user.role, **payload.model_dump())
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UserOut.model_validate(user)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, payload: UserUpdateIn, current_user: AuthenticatedUser = Depends(get_current_user)
) -> UserOut:
    try:
        user = AuthController().update_user(actor_role=current_user.role, user_id=user_id, **payload.model_dump())
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UserOut.model_validate(user)


@router.post("/{user_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(user_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> None:
    try:
        AuthController().set_user_active(actor_role=current_user.role, user_id=user_id, is_active=False)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{user_id}/reactivate", status_code=status.HTTP_204_NO_CONTENT)
def reactivate_user(user_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> None:
    try:
        AuthController().set_user_active(actor_role=current_user.role, user_id=user_id, is_active=True)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
