"""Farm endpoints. Mirrors FarmController exactly — visibility scoping
(Admin/Farm Owner/Employee) is enforced there, identically to the
desktop app, not reimplemented here."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.schemas import FarmCreateIn, FarmDetailOut, FarmSummaryOut, FarmUpdateIn, UserOptionOut
from api.security import get_current_user
from controllers.auth_controller import AuthenticatedUser
from controllers.farm_controller import FarmController
from utils.exceptions import AppError

router = APIRouter(prefix="/farms", tags=["farms"])


@router.get("", response_model=List[FarmSummaryOut])
def list_farms(current_user: AuthenticatedUser = Depends(get_current_user)) -> List[FarmSummaryOut]:
    farms = FarmController().list_farms(current_user)
    return [FarmSummaryOut.model_validate(f) for f in farms]


@router.get("/owner-options", response_model=List[UserOptionOut])
def list_owner_options(current_user: AuthenticatedUser = Depends(get_current_user)) -> List[UserOptionOut]:
    """Only Admins get results here — Farm Owners are auto-assigned as
    their own farm's owner and never need to pick one."""
    options = FarmController().list_farm_owner_options(current_user)
    return [UserOptionOut.model_validate(o) for o in options]


@router.post("", response_model=FarmDetailOut)
def create_farm(
    payload: FarmCreateIn, current_user: AuthenticatedUser = Depends(get_current_user)
) -> FarmDetailOut:
    try:
        farm = FarmController().create_farm(current_user, **payload.model_dump())
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return FarmDetailOut.model_validate(farm)


@router.get("/{farm_id}", response_model=FarmDetailOut)
def get_farm(farm_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> FarmDetailOut:
    try:
        farm = FarmController().get_farm(current_user, farm_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FarmDetailOut.model_validate(farm)


@router.put("/{farm_id}", response_model=FarmDetailOut)
def update_farm(
    farm_id: int, payload: FarmUpdateIn, current_user: AuthenticatedUser = Depends(get_current_user)
) -> FarmDetailOut:
    try:
        farm = FarmController().update_farm(current_user, farm_id, **payload.model_dump())
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return FarmDetailOut.model_validate(farm)


@router.delete("/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_farm(farm_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> None:
    try:
        FarmController().delete_farm(current_user, farm_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{farm_id}/photo", response_model=FarmDetailOut)
def upload_farm_photo(
    farm_id: int, file: UploadFile = File(...), current_user: AuthenticatedUser = Depends(get_current_user)
) -> FarmDetailOut:
    controller = FarmController()
    try:
        current = controller.get_farm(current_user, farm_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    suffix = Path(file.filename or "").suffix or ".jpg"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(file.file.read())
        farm = controller.update_farm(
            current_user,
            farm_id,
            name=current.name,
            phone_number=current.phone_number,
            address=current.address,
            gps_latitude=current.gps_latitude,
            gps_longitude=current.gps_longitude,
            notes=current.notes,
            photo_source_path=Path(tmp_path),
        )
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        os.unlink(tmp_path)
    return FarmDetailOut.model_validate(farm)
