"""Farm endpoints. Mirrors FarmController exactly — visibility scoping
(Admin/Farm Owner/Employee) is enforced there, identically to the
desktop app, not reimplemented here."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas import FarmDetailOut, FarmSummaryOut
from api.security import get_current_user
from controllers.auth_controller import AuthenticatedUser
from controllers.farm_controller import FarmController
from utils.exceptions import AppError

router = APIRouter(prefix="/farms", tags=["farms"])


@router.get("", response_model=List[FarmSummaryOut])
def list_farms(current_user: AuthenticatedUser = Depends(get_current_user)) -> List[FarmSummaryOut]:
    farms = FarmController().list_farms(current_user)
    return [FarmSummaryOut.model_validate(f) for f in farms]


@router.get("/{farm_id}", response_model=FarmDetailOut)
def get_farm(farm_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> FarmDetailOut:
    try:
        farm = FarmController().get_farm(current_user, farm_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FarmDetailOut.model_validate(farm)
