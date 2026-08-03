"""AI-assisted insights: lactation curve analysis, milk yield/quality
trends, a Fat:Protein ratio health flag, a next-breeding recommendation,
and structured AI alerts.

The breeding math and the "ideal ~160-day average milking days" target
follow standard dairy-herd-management theory: with a target calving
interval of ~380 days and a ~60-day dry period, the productive (milking)
window per lactation is ~320 days and the herd-wide average milking-days
figure should track ~160 days. The Fat:Protein ratio thresholds (>=1.5
elevated, <=1.0 low for cattle; species-adjusted for buffalo) are the
standard subclinical-ketosis / rumen-acidosis screening heuristics used
in herd testing programs — not a diagnosis, just a flag for the farmer
to investigate further.

The "ideal lactation curve" is Wood's incomplete gamma function model
(y = a * t^b * e^(-c*t)), the standard parametric model for dairy
lactation curves, with textbook shape parameters (b=0.2, c=0.003 → a
peak at day ~67, matching typical 45-70 day peak timing) and `a` scaled
so the ideal curve's peak matches the cow's own observed peak — this
compares *shape* (how fast a cow rises to and falls from peak) rather
than absolute yield, which varies hugely by breed/animal.

This is all deliberately simple, explainable arithmetic over the
farmer's own recorded data (not a trained model) — the same "start with
clear statistical rules" approach `ai/ai_service.py` documents for the
whole AI layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from controllers.auth_controller import AuthenticatedUser
from controllers.base_controller import BaseController
from controllers.calf_birth_controller import CalfBirthController
from controllers.daily_record_controller import DailyRecordController
from controllers.farm_access import ensure_can_access_farm, get_cow_or_raise, get_farm_or_raise
from controllers.milk_quality_controller import MilkQualityController
from database.session import get_db_session
from models.cow import PregnancyStatus
from services.cow_service import CowService
from services.farm_service import FarmService

IDEAL_CALVING_INTERVAL_DAYS = 380
IDEAL_DRY_DAYS = 60
IDEAL_AVG_MILKING_DAYS = (IDEAL_CALVING_INTERVAL_DAYS - IDEAL_DRY_DAYS) // 2  # ~160

VOLUNTARY_WAIT_DAYS = 50
BREEDING_TARGET_DAYS = 97  # last-calving + this ≈ a 380-day interval given ~283-day gestation
BREEDING_OVERDUE_DAYS = 130
DRY_OFF_REMINDER_DAYS = 60  # start reminding this many days before expected calving

FAT_PROTEIN_HIGH = 1.5
FAT_PROTEIN_LOW = 1.0

# Buffalo milk naturally runs higher fat relative to protein than cow milk
# (~6-8% fat, ~3.5-4.5% protein vs cattle's ~3.5-4.5% / ~3-3.5%), so a
# ratio that would flag negative energy balance in a cow is normal for a
# healthy buffalo. Detected from the breed string (see `_fat_protein_flag`)
# rather than a dedicated species field, since none exists on Cow yet.
FAT_PROTEIN_HIGH_BUFFALO = 2.2
FAT_PROTEIN_LOW_BUFFALO = 1.3

LOW_FAT_PERCENT = 3.0
LOW_PROTEIN_PERCENT = 2.8
FEVER_TEMP_C = 39.4

# Wood's incomplete gamma lactation curve shape parameters.
WOOD_B = 0.2
WOOD_C = 0.003
WOOD_PEAK_DIM = WOOD_B / WOOD_C  # ~66.7 days

RECORD_HISTORY_LIMIT = 310  # covers a full ~305-day lactation plus buffer


@dataclass(frozen=True)
class MilkYieldPoint:
    record_date: date
    morning_liters: Optional[float]
    evening_liters: Optional[float]
    total_liters: Optional[float]


@dataclass(frozen=True)
class QualityPoint:
    test_date: date
    fat_percent: Optional[float]
    snf_percent: Optional[float]
    protein_percent: Optional[float]


@dataclass(frozen=True)
class BreedingOutlook:
    status: str  # "already_pregnant" | "too_early" | "ready" | "overdue" | "no_data"
    last_calving_date: Optional[date]
    days_since_calving: Optional[int]
    window_start: Optional[date]
    window_target: Optional[date]
    message: str


@dataclass(frozen=True)
class LactationPoint:
    days_in_milk: int
    record_date: date
    actual_liters: Optional[float]
    ideal_liters: float


@dataclass(frozen=True)
class LactationPeak:
    days_in_milk: int
    record_date: date
    liters: float


@dataclass(frozen=True)
class LactationCurve:
    points: List[LactationPoint]
    peak: Optional[LactationPeak]
    average_liters: Optional[float]
    status: str  # "normal" | "abnormal" | "no_data"
    note: str


@dataclass(frozen=True)
class Alert:
    title: str
    reason: str
    confidence: int  # 0-100, rule-based (not a trained-model probability)
    action: str
    priority: str  # "info" | "warning" | "critical"


@dataclass(frozen=True)
class CowInsights:
    cow_id: int
    milk_yield_series: List[MilkYieldPoint]
    quality_series: List[QualityPoint]
    latest_fat_protein_ratio: Optional[float]
    fat_protein_flag: str  # "good" | "high" | "low" | "unknown"
    ideal_avg_milking_days: int
    breeding: BreedingOutlook
    lactation_curve: LactationCurve
    alerts: List[Alert]


class InsightsController(BaseController):
    def get_cow_insights(self, actor: AuthenticatedUser, cow_id: int) -> CowInsights:
        with get_db_session() as session:
            farm_service = FarmService(session)
            cow = get_cow_or_raise(CowService(session), cow_id)
            farm = get_farm_or_raise(farm_service, cow.farm_id)
            ensure_can_access_farm(farm_service, actor, farm)
            is_buffalo = "buffalo" in cow.breed.lower()

        records = DailyRecordController().list_for_cow(actor, cow_id, limit=RECORD_HISTORY_LIMIT)
        quality_tests = MilkQualityController().list_for_cow(actor, cow_id, limit=30)
        births = CalfBirthController().list_for_mother(actor, cow_id)

        yield_series = [
            MilkYieldPoint(
                record_date=r.record_date,
                morning_liters=r.milk_morning_liters,
                evening_liters=r.milk_evening_liters,
                total_liters=r.total_milk_liters,
            )
            for r in reversed(records)
        ]
        quality_series = [
            QualityPoint(test_date=t.test_date, fat_percent=t.fat_percent, snf_percent=t.snf_percent, protein_percent=t.protein_percent)
            for t in reversed(quality_tests)
        ]

        ratio, flag = self._fat_protein_flag(quality_tests[0] if quality_tests else None, is_buffalo)
        last_calving = max((b.birth_date for b in births), default=None)
        breeding = self._breeding_outlook(cow, last_calving)
        lactation_curve = self._lactation_curve(records, last_calving)
        alerts = self._build_alerts(records, quality_tests, ratio, flag, breeding, lactation_curve, cow, is_buffalo)

        return CowInsights(
            cow_id=cow_id,
            milk_yield_series=yield_series,
            quality_series=quality_series,
            latest_fat_protein_ratio=ratio,
            fat_protein_flag=flag,
            ideal_avg_milking_days=IDEAL_AVG_MILKING_DAYS,
            breeding=breeding,
            lactation_curve=lactation_curve,
            alerts=alerts,
        )

    # ---- Fat:Protein ratio ---------------------------------------------------

    @staticmethod
    def _fat_protein_flag(latest_test, is_buffalo: bool) -> tuple[Optional[float], str]:
        if latest_test is None or not latest_test.fat_percent or not latest_test.protein_percent:
            return None, "unknown"
        ratio = round(latest_test.fat_percent / latest_test.protein_percent, 2)
        high = FAT_PROTEIN_HIGH_BUFFALO if is_buffalo else FAT_PROTEIN_HIGH
        low = FAT_PROTEIN_LOW_BUFFALO if is_buffalo else FAT_PROTEIN_LOW
        if ratio >= high:
            return ratio, "high"
        if ratio <= low:
            return ratio, "low"
        return ratio, "good"

    # ---- Breeding recommendation ---------------------------------------------

    @staticmethod
    def _breeding_outlook(cow, last_calving: Optional[date]) -> BreedingOutlook:
        today = date.today()

        if cow.pregnancy_status == PregnancyStatus.PREGNANT:
            due = cow.expected_delivery_date
            message = (
                f"Already confirmed pregnant — expected delivery {due}."
                if due
                else "Already confirmed pregnant."
            )
            return BreedingOutlook("already_pregnant", None, None, None, None, message)

        if last_calving is None:
            return BreedingOutlook(
                "no_data", None, None, None, None,
                "No calving history on file yet — log a calf birth to get a breeding window recommendation.",
            )

        days_since = (today - last_calving).days
        window_start = last_calving + timedelta(days=VOLUNTARY_WAIT_DAYS)
        window_target = last_calving + timedelta(days=BREEDING_TARGET_DAYS)

        if days_since < VOLUNTARY_WAIT_DAYS:
            message = f"Voluntary waiting period — breeding not recommended until {window_start} (day {VOLUNTARY_WAIT_DAYS})."
            status = "too_early"
        elif days_since <= BREEDING_OVERDUE_DAYS:
            message = f"In the breeding window. Target rebreeding by {window_target} to hold a ~{IDEAL_CALVING_INTERVAL_DAYS}-day calving interval."
            status = "ready"
        else:
            message = f"Overdue — {days_since} days since calving. Breeding soon is recommended to avoid an extended calving interval."
            status = "overdue"

        return BreedingOutlook(status, last_calving, days_since, window_start, window_target, message)

    # ---- Lactation curve -------------------------------------------------------

    @staticmethod
    def _wood_ideal(dim: int, peak_liters: float) -> float:
        """Wood's incomplete gamma function, scaled so its own peak equals
        `peak_liters` — gives a same-peak reference shape to compare against."""
        t = max(dim, 1)
        peak_value = (WOOD_PEAK_DIM ** WOOD_B) * (2.718281828 ** (-WOOD_C * WOOD_PEAK_DIM))
        a = peak_liters / peak_value if peak_value > 0 else 0
        return round(a * (t ** WOOD_B) * (2.718281828 ** (-WOOD_C * t)), 2)

    @classmethod
    def _lactation_curve(cls, records, last_calving: Optional[date]) -> LactationCurve:
        if last_calving is None:
            return LactationCurve(points=[], peak=None, average_liters=None, status="no_data",
                                   note="No calving date on file — log a calf birth to unlock the lactation curve.")

        dated = [(r.record_date, r.total_milk_liters) for r in records if r.record_date >= last_calving]
        dated.sort(key=lambda x: x[0])
        if len(dated) < 5:
            return LactationCurve(points=[], peak=None, average_liters=None, status="no_data",
                                   note="Not enough milking records since the last calving yet to plot a curve.")

        actual_points = [(d, (d - last_calving).days, liters) for d, liters in dated if liters is not None]
        if not actual_points:
            return LactationCurve(points=[], peak=None, average_liters=None, status="no_data", note="No milk yield recorded yet this lactation.")

        peak_date, peak_dim, peak_liters = max(actual_points, key=lambda p: p[2])
        average = round(sum(p[2] for p in actual_points) / len(actual_points), 2)

        points = [
            LactationPoint(days_in_milk=dim, record_date=d, actual_liters=liters, ideal_liters=cls._wood_ideal(dim, peak_liters))
            for d, dim, liters in actual_points
        ]

        # If logging only started well into the lactation (record history
        # is shorter than the time since calving), the true early peak may
        # be missing from our data entirely — comparing peak *timing*
        # against the day-45-70 norm would then be misleading, so that
        # specific check is skipped and the gap is called out instead.
        earliest_dim = actual_points[0][1]
        history_gap = earliest_dim > 30
        status, note = cls._assess_lactation(peak_dim, actual_points, history_gap)

        return LactationCurve(
            points=points,
            peak=LactationPeak(days_in_milk=peak_dim, record_date=peak_date, liters=peak_liters),
            average_liters=average,
            status=status,
            note=note,
        )

    @staticmethod
    def _assess_lactation(peak_dim: int, actual_points, history_gap: bool) -> tuple[str, str]:
        note: Optional[str] = None
        if history_gap:
            note = (
                f"Recording started on day {actual_points[0][1]} of this lactation, so the true early peak "
                "may not be in the data — peak-timing analysis is skipped, but the shape from here is still tracked."
            )
        elif peak_dim < 15:
            return "abnormal", f"Peak occurred unusually early (day {peak_dim}) — typical peak is around day 45-70. Worth reviewing early-lactation nutrition."
        elif peak_dim > 110:
            return "abnormal", f"Peak occurred unusually late (day {peak_dim}) — typical peak is around day 45-70."

        post_peak = [p for p in actual_points if p[1] > peak_dim]
        if len(post_peak) >= 14:
            first_week_avg = sum(p[2] for p in post_peak[:7]) / min(7, len(post_peak))
            last_week_avg = sum(p[2] for p in post_peak[-7:]) / min(7, len(post_peak[-7:]))
            weeks_between = max((post_peak[-1][1] - post_peak[0][1]) / 7, 1)
            weekly_decline_pct = (1 - (last_week_avg / first_week_avg)) / weeks_between * 100 if first_week_avg > 0 else 0
            if weekly_decline_pct > 4:
                return "abnormal", f"Post-peak decline is steep (~{round(weekly_decline_pct, 1)}%/week) — ideal persistence is under ~2.5%/week. Check nutrition and health."

        return "normal", note or f"Peak on day {peak_dim} and post-peak decline are within a normal range."

    # ---- AI Alerts -------------------------------------------------------------

    @classmethod
    def _build_alerts(cls, records, quality_tests, ratio, flag, breeding, lactation, cow, is_buffalo) -> List[Alert]:
        alerts: List[Alert] = []
        high = FAT_PROTEIN_HIGH_BUFFALO if is_buffalo else FAT_PROTEIN_HIGH
        low = FAT_PROTEIN_LOW_BUFFALO if is_buffalo else FAT_PROTEIN_LOW

        recent = [r.total_milk_liters for r in records[:7] if r.total_milk_liters is not None]
        previous = [r.total_milk_liters for r in records[7:14] if r.total_milk_liters is not None]
        recent_temps = [r.body_temperature_c for r in records[:5] if r.body_temperature_c is not None]
        fever = any(t >= FEVER_TEMP_C for t in recent_temps)
        yield_drop_pct = None
        if recent and previous:
            recent_avg = sum(recent) / len(recent)
            previous_avg = sum(previous) / len(previous)
            if previous_avg > 0 and recent_avg < previous_avg * 0.9:
                yield_drop_pct = round((1 - recent_avg / previous_avg) * 100)

        if yield_drop_pct and fever:
            alerts.append(Alert(
                title="Possible Mastitis",
                reason=f"Milk yield dropped {yield_drop_pct}% this week alongside a recent fever reading (≥{FEVER_TEMP_C}°C).",
                confidence=75, priority="critical",
                action="Check the udder for heat, swelling, or abnormal milk, and consider a vet visit.",
            ))
        elif yield_drop_pct:
            alerts.append(Alert(
                title="Milk Yield Drop",
                reason=f"Milk yield is down {yield_drop_pct}% over the last week compared to the week before.",
                confidence=65, priority="warning",
                action="Review feed intake, water access, and recent health/vaccination events.",
            ))

        if fever:
            alerts.append(Alert(
                title="Health Risk — Elevated Temperature",
                reason=f"Recent body temperature reading(s) at or above {FEVER_TEMP_C}°C.",
                confidence=70, priority="critical",
                action="Monitor closely and consult a veterinarian if it persists.",
            ))

        recent_heat = any(r.heat_detected for r in records[:5])
        if recent_heat and cow.pregnancy_status.value == "open":
            alerts.append(Alert(
                title="Possible Heat Detected",
                reason="Heat was logged in a recent daily record and the cow is currently open.",
                confidence=60, priority="info",
                action="Confirm standing heat and plan insemination timing (12-18 hours after standing heat begins).",
            ))

        if flag == "high":
            alerts.append(Alert(
                title="Elevated Fat:Protein Ratio",
                reason=f"Latest ratio is {ratio} (≥{high}) — a marker for possible negative energy balance / subclinical ketosis.",
                confidence=60, priority="warning",
                action="Check body condition score and review early-lactation energy intake.",
            ))
        elif flag == "low":
            alerts.append(Alert(
                title="Low Fat:Protein Ratio",
                reason=f"Latest ratio is {ratio} (≤{low}) — a marker for possible rumen acidosis.",
                confidence=55, priority="warning",
                action="Review fiber intake and feeding routine.",
            ))

        latest_quality = quality_tests[0] if quality_tests else None
        if latest_quality and latest_quality.fat_percent is not None and latest_quality.fat_percent < LOW_FAT_PERCENT:
            alerts.append(Alert(
                title="Low Fat %",
                reason=f"Latest fat reading is {latest_quality.fat_percent}%, below the {LOW_FAT_PERCENT}% floor.",
                confidence=60, priority="warning",
                action="Review forage quality and fiber intake.",
            ))
        if latest_quality and latest_quality.protein_percent is not None and latest_quality.protein_percent < LOW_PROTEIN_PERCENT:
            alerts.append(Alert(
                title="Low Protein %",
                reason=f"Latest protein reading is {latest_quality.protein_percent}%, below the {LOW_PROTEIN_PERCENT}% floor.",
                confidence=60, priority="warning",
                action="Review energy and protein content of the ration.",
            ))

        if lactation.status == "abnormal":
            alerts.append(Alert(
                title="Abnormal Lactation Curve",
                reason=lactation.note,
                confidence=55, priority="warning",
                action="Compare against herd average and review nutrition/health history for this lactation.",
            ))

        if breeding.status == "overdue":
            alerts.append(Alert(
                title="Breeding Overdue",
                reason=breeding.message,
                confidence=70, priority="warning",
                action="Schedule a heat check and plan for insemination.",
            ))

        if cow.pregnancy_status.value == "pregnant" and cow.expected_delivery_date:
            days_to_calving = (cow.expected_delivery_date - date.today()).days
            if 0 <= days_to_calving <= DRY_OFF_REMINDER_DAYS and records and records[0].total_milk_liters:
                alerts.append(Alert(
                    title="Dry Period Due",
                    reason=f"Expected calving in {days_to_calving} days and still being milked — ideal dry period is ~{IDEAL_DRY_DAYS} days before calving.",
                    confidence=80, priority="warning",
                    action=f"Plan to dry off around {cow.expected_delivery_date - timedelta(days=IDEAL_DRY_DAYS)}.",
                ))

        return alerts
