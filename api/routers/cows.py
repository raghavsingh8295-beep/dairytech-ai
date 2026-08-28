"""Cow endpoints. Mirrors CowController exactly — farm-scoped visibility
is enforced there, identically to the desktop app, not reimplemented here."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.schemas import CowCreateIn, CowDetailOut, CowSummaryOut, CowUpdateIn
from api.security import get_current_user
from controllers.auth_controller import AuthenticatedUser
from controllers.cow_controller import CowController
from utils.exceptions import AppError

router = APIRouter(tags=["cows"])


@router.get("/farms/{farm_id}/cows", response_model=List[CowSummaryOut])
def list_cows_for_farm(
    farm_id: int, current_user: AuthenticatedUser = Depends(get_current_user)
) -> List[CowSummaryOut]:
    try:
        cows = CowController().list_cows(current_user, farm_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [CowSummaryOut.model_validate(c) for c in cows]


@router.post("/farms/{farm_id}/cows", response_model=CowDetailOut)
def create_cow(
    farm_id: int, payload: CowCreateIn, current_user: AuthenticatedUser = Depends(get_current_user)
) -> CowDetailOut:
    try:
        cow = CowController().create_cow(current_user, farm_id=farm_id, **payload.model_dump())
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CowDetailOut.model_validate(cow)


@router.get("/cows/{cow_id}", response_model=CowDetailOut)
def get_cow(cow_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> CowDetailOut:
    try:
        cow = CowController().get_cow(current_user, cow_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CowDetailOut.model_validate(cow)


@router.put("/cows/{cow_id}", response_model=CowDetailOut)
def update_cow(
    cow_id: int, payload: CowUpdateIn, current_user: AuthenticatedUser = Depends(get_current_user)
) -> CowDetailOut:
    try:
        cow = CowController().update_cow(current_user, cow_id, **payload.model_dump())
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CowDetailOut.model_validate(cow)


@router.delete("/cows/{cow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cow(cow_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> None:
    try:
        CowController().delete_cow(current_user, cow_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/cows/{cow_id}/photo", response_model=CowDetailOut)
def upload_cow_photo(
    cow_id: int, file: UploadFile = File(...), current_user: AuthenticatedUser = Depends(get_current_user)
) -> CowDetailOut:
    controller = CowController()
    try:
        current = controller.get_cow(current_user, cow_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    suffix = Path(file.filename or "").suffix or ".jpg"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(file.file.read())
        cow = controller.update_cow(
            current_user,
            cow_id,
            tag_number=current.tag_number,
            breed=current.breed,
            gender=current.gender,
            birth_date=current.birth_date,
            rfid_number=current.rfid_number,
            weight_kg=current.weight_kg,
            height_cm=current.height_cm,
            color=current.color,
            horn_type=current.horn_type,
            pregnancy_status=current.pregnancy_status,
            expected_delivery_date=current.expected_delivery_date,
            calving_date=current.calving_date,
            health_status=current.health_status,
            purchase_date=current.purchase_date,
            purchase_price=current.purchase_price,
            location=current.location,
            notes=current.notes,
            photo_source_path=Path(tmp_path),
        )
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        os.unlink(tmp_path)
    return CowDetailOut.model_validate(cow)
