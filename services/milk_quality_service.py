from __future__ import annotations

from datetime import date
from typing import List, Optional

from sqlalchemy import select

from models.milk_quality import MilkQualityTest, MilkSession
from services.base_service import BaseService


class MilkQualityService(BaseService[MilkQualityTest]):
    model = MilkQualityTest

    def get_for_cow_date_session(
        self, cow_id: int, test_date: date, session: MilkSession
    ) -> Optional[MilkQualityTest]:
        stmt = select(MilkQualityTest).where(
            MilkQualityTest.cow_id == cow_id,
            MilkQualityTest.test_date == test_date,
            MilkQualityTest.session == session,
            MilkQualityTest.is_active.is_(True),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_any_for_cow_date_session(
        self, cow_id: int, test_date: date, session: MilkSession
    ) -> Optional[MilkQualityTest]:
        """Like `get_for_cow_date_session` but matches regardless of
        `is_active`. The (cow, date, session) triple is DB-unique, so a
        soft-deleted row still occupies that slot — `save_test`'s upsert
        must find it and revive it, or it hits the unique constraint
        trying to INSERT a duplicate."""
        stmt = select(MilkQualityTest).where(
            MilkQualityTest.cow_id == cow_id,
            MilkQualityTest.test_date == test_date,
            MilkQualityTest.session == session,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_for_cow(
        self,
        cow_id: int,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> List[MilkQualityTest]:
        stmt = select(MilkQualityTest).where(
            MilkQualityTest.cow_id == cow_id, MilkQualityTest.is_active.is_(True)
        )
        if start_date is not None:
            stmt = stmt.where(MilkQualityTest.test_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(MilkQualityTest.test_date <= end_date)
        stmt = stmt.order_by(MilkQualityTest.test_date.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.execute(stmt).scalars().all())
