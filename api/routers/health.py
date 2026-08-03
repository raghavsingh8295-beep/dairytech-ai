"""Health quick-view endpoints: diseases and vaccinations for a cow, plus
vaccinations due/overdue within a reminder window. Mirrors
DiseaseController/VaccinationController exactly.

VaccinationEntry.is_overdue takes an `as_of` argument, so unlike every
other field it can't be auto-mapped by Pydantic's from_attributes — it's
computed here per-entry against today's date before validation.
"""
from __future__ import annotations

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.schemas import DiseaseCreateIn, DiseaseOut, VaccinationCreateIn, VaccinationOut
from api.security import get_current_user
from controllers.auth_controller import AuthenticatedUser
from controllers.disease_controller import DiseaseController
from controllers.vaccination_controller import VaccinationController, VaccinationEntry
from utils.exceptions import AppError

router = APIRouter(tags=["health"])


def _vaccination_out(entry: VaccinationEntry) -> VaccinationOut:
    return VaccinationOut(
        id=entry.id,
        cow_id=entry.cow_id,
        vaccine_name=entry.vaccine_name,
        scheduled_date=entry.scheduled_date,
        date_given=entry.date_given,
        administered_by=entry.administered_by,
        cost=entry.cost,
        notes=entry.notes,
        recorded_by_name=entry.recorded_by_name,
        is_active=entry.is_active,
        is_completed=entry.is_completed,
        is_overdue=entry.is_overdue(as_of=date.today()),
    )


@router.get("/cows/{cow_id}/diseases", response_model=List[DiseaseOut])
def list_diseases_for_cow(
    cow_id: int, current_user: AuthenticatedUser = Depends(get_current_user)
) -> List[DiseaseOut]:
    try:
        diseases = DiseaseController().list_for_cow(current_user, cow_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [DiseaseOut.model_validate(d) for d in diseases]


@router.post("/cows/{cow_id}/diseases", response_model=DiseaseOut)
def create_disease(
    cow_id: int, payload: DiseaseCreateIn, current_user: AuthenticatedUser = Depends(get_current_user)
) -> DiseaseOut:
    try:
        disease = DiseaseController().create_disease(current_user, cow_id=cow_id, **payload.model_dump())
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DiseaseOut.model_validate(disease)


@router.delete("/diseases/{disease_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_disease(disease_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> None:
    try:
        DiseaseController().delete_disease(current_user, disease_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/cows/{cow_id}/vaccinations", response_model=List[VaccinationOut])
def list_vaccinations_for_cow(
    cow_id: int, current_user: AuthenticatedUser = Depends(get_current_user)
) -> List[VaccinationOut]:
    try:
        vaccinations = VaccinationController().list_for_cow(current_user, cow_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [_vaccination_out(v) for v in vaccinations]


@router.post("/cows/{cow_id}/vaccinations", response_model=VaccinationOut)
def create_vaccination(
    cow_id: int, payload: VaccinationCreateIn, current_user: AuthenticatedUser = Depends(get_current_user)
) -> VaccinationOut:
    try:
        vaccination = VaccinationController().create_vaccination(current_user, cow_id=cow_id, **payload.model_dump())
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _vaccination_out(vaccination)


@router.delete("/vaccinations/{vaccination_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vaccination(vaccination_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> None:
    try:
        VaccinationController().delete_vaccination(current_user, vaccination_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/cows/{cow_id}/vaccinations/due", response_model=List[VaccinationOut])
def list_vaccinations_due_for_cow(
    cow_id: int,
    within_days: int = Query(default=14),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[VaccinationOut]:
    try:
        vaccinations = VaccinationController().list_due_for_cow(
            current_user, cow_id, within_days=within_days
        )
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [_vaccination_out(v) for v in vaccinations]
