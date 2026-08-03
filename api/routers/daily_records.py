"""Daily record endpoints. Mirrors DailyRecordController exactly — the
save endpoint is a full-overwrite upsert by (cow_id, record_date), not a
partial patch, same as the desktop dialog."""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.schemas import DailyRecordCreateIn, DailyRecordOut
from api.security import get_current_user
from controllers.auth_controller import AuthenticatedUser
from controllers.daily_record_controller import DailyRecordController
from utils.exceptions import AppError

router = APIRouter(tags=["daily-records"])


@router.get("/cows/{cow_id}/records", response_model=List[DailyRecordOut])
def list_records_for_cow(
    cow_id: int,
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: Optional[int] = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[DailyRecordOut]:
    try:
        records = DailyRecordController().list_for_cow(
            current_user, cow_id, start_date=start_date, end_date=end_date, limit=limit
        )
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [DailyRecordOut.model_validate(r) for r in records]


@router.post("/cows/{cow_id}/records", response_model=DailyRecordOut)
def save_record_for_cow(
    cow_id: int,
    payload: DailyRecordCreateIn,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> DailyRecordOut:
    try:
        record = DailyRecordController().save_record(
            current_user, cow_id=cow_id, **payload.model_dump()
        )
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DailyRecordOut.model_validate(record)


@router.delete("/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(record_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> None:
    try:
        DailyRecordController().delete_record(current_user, record_id)
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
