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
from controllers.cow_controller import CowController, CowSummary
from controllers.daily_record_controller import DailyRecordController
from controllers.farm_access import ensure_can_access_farm, get_farm_or_raise
from controllers.milk_quality_controller import MilkQualityController
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
class CowPerformance:
    """A cow's standing on the dashboard's best/worst-performer cards: milk
    quantity (last `RECENT_DAYS`) and fat % (most recent test) combined into
    one score by min-max normalizing each across the farm's eligible cows
    and averaging — necessary because the two measures live on completely
    different scales (liters vs. a single-digit percentage), so comparing
    or summing them raw would let whichever happens to have the bigger
    numbers dominate."""

    cow_id: int
    tag_number: str
    avg_daily_liters: float
    fat_percent: float
    score: float


@dataclass(frozen=True)
class FarmDashboardSummary:
    farm_id: int
    today_total_liters: Optional[float]
    yesterday_total_liters: Optional[float]
    recent_records: List[RecentRecordEntry]
    best_performer: Optional[CowPerformance]
    worst_performer: Optional[CowPerformance]


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

        best_performer, worst_performer = self._rank_performers(actor, cows)

        return FarmDashboardSummary(
            farm_id=farm_id,
            today_total_liters=round(today_total, 2) if today_has_data else None,
            yesterday_total_liters=round(yesterday_total, 2) if yesterday_has_data else None,
            recent_records=recent[:DASHBOARD_RECENT_LIMIT],
            best_performer=best_performer,
            worst_performer=worst_performer,
        )

    @staticmethod
    def _rank_performers(
        actor: AuthenticatedUser, cows: List[CowSummary]
    ) -> tuple[Optional[CowPerformance], Optional[CowPerformance]]:
        """Combines each cow's recent milk quantity with its most recent fat
        % test into one score (see `CowPerformance`), and returns the top
        and bottom of that ranking. A cow needs both numbers to be ranked —
        one without the other can't be compared fairly, so it's left out
        rather than guessed at."""
        candidates = []
        for cow in cows:
            if cow.gender.value != "female":
                continue
            records = DailyRecordController().list_for_cow(actor, cow.id, limit=RECENT_DAYS)
            liters = [r.total_milk_liters for r in records if r.total_milk_liters is not None]
            if not liters:
                continue
            quality = MilkQualityController().list_for_cow(actor, cow.id, limit=1)
            if not quality or quality[0].fat_percent is None:
                continue
            candidates.append((cow, sum(liters) / len(liters), quality[0].fat_percent))

        if not candidates:
            return None, None

        milk_values = [c[1] for c in candidates]
        fat_values = [c[2] for c in candidates]
        milk_lo, milk_hi = min(milk_values), max(milk_values)
        fat_lo, fat_hi = min(fat_values), max(fat_values)

        def normalize(value: float, lo: float, hi: float) -> float:
            # All candidates tied on this measure — treat it as a wash
            # rather than dividing by zero.
            return 50.0 if hi == lo else (value - lo) / (hi - lo) * 100

        ranked = sorted(
            (
                CowPerformance(
                    cow_id=cow.id,
                    tag_number=cow.tag_number,
                    avg_daily_liters=round(liters, 2),
                    fat_percent=fat,
                    score=round((normalize(liters, milk_lo, milk_hi) + normalize(fat, fat_lo, fat_hi)) / 2, 1),
                )
                for cow, liters, fat in candidates
            ),
            key=lambda p: p.score,
            reverse=True,
        )
        return ranked[0], ranked[-1]

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
