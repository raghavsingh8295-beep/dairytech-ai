from __future__ import annotations

from datetime import date
from typing import List, Optional, Sequence

from sqlalchemy import func, select

from models.cow import Cow
from models.daily_record import DailyRecord
from services.base_service import BaseService


class DailyRecordService(BaseService[DailyRecord]):
    model = DailyRecord

    def get_for_cow_and_date(self, cow_id: int, record_date: date) -> Optional[DailyRecord]:
        stmt = select(DailyRecord).where(
            DailyRecord.cow_id == cow_id,
            DailyRecord.record_date == record_date,
            DailyRecord.is_active.is_(True),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_any_for_cow_and_date(self, cow_id: int, record_date: date) -> Optional[DailyRecord]:
        """Like `get_for_cow_and_date` but matches regardless of
        `is_active`. (cow_id, record_date) is DB-unique, so a soft-deleted
        row still occupies that slot — `save_record`'s upsert must find
        and revive it, or it hits the unique constraint trying to INSERT
        a duplicate."""
        stmt = select(DailyRecord).where(
            DailyRecord.cow_id == cow_id, DailyRecord.record_date == record_date
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_for_cow(
        self,
        cow_id: int,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> List[DailyRecord]:
        stmt = select(DailyRecord).where(DailyRecord.cow_id == cow_id, DailyRecord.is_active.is_(True))
        if start_date is not None:
            stmt = stmt.where(DailyRecord.record_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(DailyRecord.record_date <= end_date)
        stmt = stmt.order_by(DailyRecord.record_date.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def latest_record_date(self, cow_id: int) -> Optional[date]:
        stmt = select(func.max(DailyRecord.record_date)).where(
            DailyRecord.cow_id == cow_id, DailyRecord.is_active.is_(True)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def sum_milk_for_farms_on_date(self, farm_ids: Sequence[int], record_date: date) -> float:
        """For the Dashboard's Milk Today card — one query across every
        farm the actor can see rather than looping per cow."""
        stmt = (
            select(
                func.coalesce(func.sum(DailyRecord.milk_morning_liters), 0.0)
                + func.coalesce(func.sum(DailyRecord.milk_evening_liters), 0.0)
            )
            .join(Cow, DailyRecord.cow_id == Cow.id)
            .where(
                Cow.farm_id.in_(farm_ids),
                DailyRecord.record_date == record_date,
                DailyRecord.is_active.is_(True),
            )
        )
        return self.session.execute(stmt).scalar_one()
