"""Farm-level herd analytics: production rankings, and pregnancy/health
status breakdowns across every cow on a farm. Aggregates over the same
per-cow data `InsightsController` and `CowController` already expose —
no new storage, just farm-wide arithmetic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.cow_controller import CowController
from controllers.daily_record_controller import DailyRecordController
from controllers.farm_access import ensure_can_access_farm, get_farm_or_raise
from database.session import get_db_session
from services.farm_service import FarmService

RECENT_DAYS = 7
DASHBOARD_RECENT_LIMIT = 8


@dataclass(frozen=True)
class CowProduction:
    cow_id: int
    tag_number: str
    breed: str
    avg_daily_liters: float


@dataclass(frozen=True)
class RecentRecordEntry:
    cow_id: int
    tag_number: str
    record_date: date
    total_liters: Optional[float]


@dataclass(frozen=True)
class FarmDashboardSummary:
    farm_id: int
    today_total_liters: Optional[float]
    yesterday_total_liters: Optional[float]
    recent_records: List[RecentRecordEntry]


@dataclass(frozen=True)
class HerdAnalytics:
    farm_id: int
    total_animals: int
    milking_animals: int
    herd_average_liters: Optional[float]
    total_herd_liters: Optional[float]
    best_producer: Optional[CowProduction]
    lowest_producer: Optional[CowProduction]
    top_producers: List[CowProduction]
    pregnant_count: int
    open_count: int
    unknown_pregnancy_count: int
    healthy_count: int
    sick_count: int
    under_treatment_count: int
    critical_count: int
    quarantined_count: int
    average_feed_intake_kg: Optional[float]


class HerdAnalyticsController(BaseController):
    def get_dashboard_summary(self, actor: AuthenticatedUser, farm_id: int) -> FarmDashboardSummary:
        """Today-vs-yesterday milk totals and a recent-activity feed across
        every cow on the farm — the numbers a farm dashboard's hero card and
        "recent records" list need, neither of which `get_farm_analytics`
        (a 7-day rolling average per cow) answers."""
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = get_farm_or_raise(farm_service, farm_id)
            ensure_can_access_farm(farm_service, actor, farm)

        cows = CowController().list_cows(actor, farm_id)
        today = date.today()
        yesterday = today - timedelta(days=1)

        today_total = 0.0
        today_has_data = False
        yesterday_total = 0.0
        yesterday_has_data = False
        recent: List[RecentRecordEntry] = []

        for cow in cows:
            window = DailyRecordController().list_for_cow(actor, cow.id, start_date=yesterday, end_date=today)
            for r in window:
                if r.total_milk_liters is None:
                    continue
                if r.record_date == today:
                    today_total += r.total_milk_liters
                    today_has_data = True
                elif r.record_date == yesterday:
                    yesterday_total += r.total_milk_liters
                    yesterday_has_data = True

            for r in DailyRecordController().list_for_cow(actor, cow.id, limit=3):
                recent.append(RecentRecordEntry(
                    cow_id=cow.id, tag_number=cow.tag_number,
                    record_date=r.record_date, total_liters=r.total_milk_liters,
                ))

        recent.sort(key=lambda e: e.record_date, reverse=True)

        return FarmDashboardSummary(
            farm_id=farm_id,
            today_total_liters=round(today_total, 2) if today_has_data else None,
            yesterday_total_liters=round(yesterday_total, 2) if yesterday_has_data else None,
            recent_records=recent[:DASHBOARD_RECENT_LIMIT],
        )

    def get_farm_analytics(self, actor: AuthenticatedUser, farm_id: int) -> HerdAnalytics:
        with get_db_session() as session:
            farm_service = FarmService(session)
            farm = get_farm_or_raise(farm_service, farm_id)
            ensure_can_access_farm(farm_service, actor, farm)

        cows = CowController().list_cows(actor, farm_id)

        productions: List[CowProduction] = []
        feed_intakes: List[float] = []
        for cow in cows:
            if cow.gender.value != "female":
                continue
            records = DailyRecordController().list_for_cow(actor, cow.id, limit=RECENT_DAYS)
            liters = [r.total_milk_liters for r in records if r.total_milk_liters is not None]
            if liters:
                productions.append(CowProduction(
                    cow_id=cow.id, tag_number=cow.tag_number, breed=cow.breed,
                    avg_daily_liters=round(sum(liters) / len(liters), 2),
                ))
            feed = [r.feed_intake_kg for r in records if r.feed_intake_kg is not None]
            feed_intakes.extend(feed)

        productions.sort(key=lambda p: p.avg_daily_liters, reverse=True)
        herd_avg = round(sum(p.avg_daily_liters for p in productions) / len(productions), 2) if productions else None
        herd_total = round(sum(p.avg_daily_liters for p in productions), 2) if productions else None

        pregnancy_counts = {"pregnant": 0, "open": 0, "unknown": 0}
        health_counts = {"healthy": 0, "sick": 0, "under_treatment": 0, "critical": 0, "quarantined": 0}
        for cow in cows:
            pregnancy_counts[cow.pregnancy_status.value] = pregnancy_counts.get(cow.pregnancy_status.value, 0) + 1
            health_counts[cow.health_status.value] = health_counts.get(cow.health_status.value, 0) + 1

        return HerdAnalytics(
            farm_id=farm_id,
            total_animals=len(cows),
            milking_animals=len(productions),
            herd_average_liters=herd_avg,
            total_herd_liters=herd_total,
            best_producer=productions[0] if productions else None,
            lowest_producer=productions[-1] if productions else None,
            top_producers=productions[:10],
            pregnant_count=pregnancy_counts["pregnant"],
            open_count=pregnancy_counts["open"],
            unknown_pregnancy_count=pregnancy_counts["unknown"],
            healthy_count=health_counts["healthy"],
            sick_count=health_counts["sick"],
            under_treatment_count=health_counts["under_treatment"],
            critical_count=health_counts["critical"],
            quarantined_count=health_counts["quarantined"],
            average_feed_intake_kg=round(sum(feed_intakes) / len(feed_intakes), 2) if feed_intakes else None,
        )
