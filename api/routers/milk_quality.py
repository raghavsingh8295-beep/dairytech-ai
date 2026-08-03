"""Milk quality test endpoints. Mirrors MilkQualityController exactly —
save is a full-overwrite upsert by (cow_id, test_date, session), same as
Daily Recording."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas import MilkQualityCreateIn, MilkQualityOut
from api.security import get_current_user
from controllers.auth_controller import AuthenticatedUser
from controllers.milk_quality_controller import MilkQualityController
from utils.exceptions import AppError

router = APIRouter(tags=["milk-quality"])


@router.get("/cows/{cow_id}/milk-quality", response_model=List[MilkQualityOut])
def list_milk_quality_for_cow(
    cow_id: int, current_user: AuthenticatedUser = Depends(get_current_user)
) -> List[MilkQualityOut]:
    try:
        tests = MilkQualityController().list_for_cow(current_user, cow_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [MilkQualityOut.model_validate(t) for t in tests]


@router.post("/cows/{cow_id}/milk-quality", response_model=MilkQualityOut)
def save_milk_quality_for_cow(
    cow_id: int, payload: MilkQualityCreateIn, current_user: AuthenticatedUser = Depends(get_current_user)
) -> MilkQualityOut:
    try:
        test = MilkQualityController().save_test(current_user, cow_id=cow_id, **payload.model_dump())
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MilkQualityOut.model_validate(test)


@router.delete("/milk-quality/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_milk_quality_test(test_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> None:
    try:
        MilkQualityController().delete_test(current_user, test_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
