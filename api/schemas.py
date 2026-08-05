"""API request/response models.

Deliberately a separate layer from the controllers' own dataclasses
(`FarmSummary`, `AuthenticatedUser`, ...) even though the fields mirror
each other closely — this is the same seam the desktop UI has via those
dataclasses sitting between it and the ORM models. `model_config =
ConfigDict(from_attributes=True)` lets each response model be built
directly from a controller dataclass via `.model_validate(...)`, no
manual field-by-field mapping needed.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from models.cow import CowGender, HealthStatus, HornType, PregnancyStatus
from models.health import DiseaseSeverity, DiseaseStatus
from models.milk_quality import MilkSession, QualityGrade
from models.user import UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


class SignUpIn(BaseModel):
    """Public self-service registration — deliberately has no `role` field
    (unlike `UserCreateIn`, used by the admin-only /users endpoint): a
    self-signup always becomes a Farm Owner, never Admin/Employee, so the
    role can't be chosen by the caller."""

    username: str
    email: str
    full_name: str
    password: str
    security_question: str
    security_answer: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    email: str
    role: UserRole
    is_active: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreateIn(BaseModel):
    username: str
    email: str
    full_name: str
    password: str
    role: UserRole
    security_question: str
    security_answer: str


class UserUpdateIn(BaseModel):
    full_name: str
    email: str


class FarmSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    owner_name: str
    phone_number: Optional[str]
    address: Optional[str]
    photo_path: Optional[str]
    employee_count: int
    cow_count: int
    is_active: bool


class FarmDetailOut(FarmSummaryOut):
    gps_latitude: Optional[float]
    gps_longitude: Optional[float]
    notes: Optional[str]


class UserOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str


class FarmCreateIn(BaseModel):
    name: str
    owner_id: Optional[int] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    notes: Optional[str] = None


class FarmUpdateIn(BaseModel):
    name: str
    owner_id: Optional[int] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    notes: Optional[str] = None


class CowSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    farm_id: int
    tag_number: str
    breed: str
    gender: CowGender
    health_status: HealthStatus
    pregnancy_status: PregnancyStatus
    photo_path: Optional[str]
    age_years: Optional[float]
    is_active: bool


class CowDetailOut(CowSummaryOut):
    rfid_number: Optional[str]
    qr_code_value: str
    qr_code_path: Optional[str]
    birth_date: Optional[date]
    weight_kg: Optional[float]
    height_cm: Optional[float]
    color: Optional[str]
    horn_type: Optional[HornType]
    expected_delivery_date: Optional[date]
    purchase_date: Optional[date]
    purchase_price: Optional[float]
    location: Optional[str]
    notes: Optional[str]


class DailyRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cow_id: int
    record_date: date
    milk_morning_liters: Optional[float]
    milk_evening_liters: Optional[float]
    total_milk_liters: Optional[float]
    weight_kg: Optional[float]
    body_temperature_c: Optional[float]
    heart_rate_bpm: Optional[int]
    rumination_minutes: Optional[float]
    activity_level: Optional[float]
    feed_intake_kg: Optional[float]
    water_intake_liters: Optional[float]
    medicine_given: Optional[str]
    vaccination_given: Optional[str]
    disease_note: Optional[str]
    pregnancy_status: Optional[PregnancyStatus]
    heat_detected: bool
    body_condition_score: Optional[float]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool
    updated_at: datetime


class DailyRecordCreateIn(BaseModel):
    record_date: date
    milk_morning_liters: Optional[float] = None
    milk_evening_liters: Optional[float] = None
    weight_kg: Optional[float] = None
    body_temperature_c: Optional[float] = None
    heart_rate_bpm: Optional[int] = None
    rumination_minutes: Optional[float] = None
    activity_level: Optional[float] = None
    feed_intake_kg: Optional[float] = None
    water_intake_liters: Optional[float] = None
    medicine_given: Optional[str] = None
    vaccination_given: Optional[str] = None
    disease_note: Optional[str] = None
    pregnancy_status: Optional[PregnancyStatus] = None
    heat_detected: bool = False
    body_condition_score: Optional[float] = None
    notes: Optional[str] = None


class DiseaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cow_id: int
    disease_name: str
    diagnosed_date: date
    severity: DiseaseSeverity
    status: DiseaseStatus
    recovery_date: Optional[date]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class DiseaseCreateIn(BaseModel):
    disease_name: str
    diagnosed_date: date
    severity: DiseaseSeverity
    status: DiseaseStatus = DiseaseStatus.ACTIVE
    recovery_date: Optional[date] = None
    notes: Optional[str] = None


class VaccinationCreateIn(BaseModel):
    vaccine_name: str
    scheduled_date: date
    date_given: Optional[date] = None
    administered_by: Optional[str] = None
    cost: Optional[float] = None
    notes: Optional[str] = None


class VaccinationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cow_id: int
    vaccine_name: str
    scheduled_date: date
    date_given: Optional[date]
    administered_by: Optional[str]
    cost: Optional[float]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool
    is_completed: bool
    is_overdue: bool


class CowCreateIn(BaseModel):
    tag_number: str
    breed: str
    gender: CowGender
    birth_date: Optional[date] = None
    rfid_number: Optional[str] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    color: Optional[str] = None
    horn_type: Optional[HornType] = None
    pregnancy_status: PregnancyStatus = PregnancyStatus.OPEN
    expected_delivery_date: Optional[date] = None
    health_status: HealthStatus = HealthStatus.HEALTHY
    purchase_date: Optional[date] = None
    purchase_price: Optional[float] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class CowUpdateIn(CowCreateIn):
    pass


class MilkQualityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cow_id: int
    test_date: date
    session: MilkSession
    fat_percent: Optional[float]
    snf_percent: Optional[float]
    protein_percent: Optional[float]
    density: Optional[float]
    bacteria_count: Optional[int]
    quality_grade: Optional[QualityGrade]
    notes: Optional[str]
    recorded_by_name: str
    is_active: bool


class MilkQualityCreateIn(BaseModel):
    test_date: date
    session_type: MilkSession = MilkSession.COMPOSITE
    fat_percent: Optional[float] = None
    snf_percent: Optional[float] = None
    protein_percent: Optional[float] = None
    density: Optional[float] = None
    bacteria_count: Optional[int] = None
    quality_grade: Optional[QualityGrade] = None
    notes: Optional[str] = None


class MilkYieldPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    record_date: date
    morning_liters: Optional[float]
    evening_liters: Optional[float]
    total_liters: Optional[float]


class QualityPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    test_date: date
    fat_percent: Optional[float]
    snf_percent: Optional[float]
    protein_percent: Optional[float]


class BreedingOutlookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    last_calving_date: Optional[date]
    days_since_calving: Optional[int]
    window_start: Optional[date]
    window_target: Optional[date]
    message: str


class LactationPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    days_in_milk: int
    record_date: date
    actual_liters: Optional[float]
    ideal_liters: float


class LactationPeakOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    days_in_milk: int
    record_date: date
    liters: float


class LactationCurveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    points: List[LactationPointOut]
    peak: Optional[LactationPeakOut]
    average_liters: Optional[float]
    status: str
    note: str


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    reason: str
    confidence: int
    action: str
    priority: str


class CowInsightsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cow_id: int
    milk_yield_series: List[MilkYieldPointOut]
    quality_series: List[QualityPointOut]
    latest_fat_protein_ratio: Optional[float]
    fat_protein_flag: str
    ideal_avg_milking_days: int
    breeding: BreedingOutlookOut
    lactation_curve: LactationCurveOut
    alerts: List[AlertOut]


class CowProductionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cow_id: int
    tag_number: str
    breed: str
    avg_daily_liters: float


class HerdAnalyticsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    farm_id: int
    total_animals: int
    milking_animals: int
    herd_average_liters: Optional[float]
    total_herd_liters: Optional[float]
    best_producer: Optional[CowProductionOut]
    lowest_producer: Optional[CowProductionOut]
    top_producers: List[CowProductionOut]
    pregnant_count: int
    open_count: int
    unknown_pregnancy_count: int
    healthy_count: int
    sick_count: int
    under_treatment_count: int
    critical_count: int
    quarantined_count: int
    average_feed_intake_kg: Optional[float]


class RecentRecordEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cow_id: int
    tag_number: str
    record_date: date
    total_liters: Optional[float]


class FarmDashboardSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    farm_id: int
    today_total_liters: Optional[float]
    yesterday_total_liters: Optional[float]
    recent_records: List[RecentRecordEntryOut]


class AssistantAskIn(BaseModel):
    question: str


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    book_title: str
    page_number: int


class AssistantAskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    answer: str
    citations: List[CitationOut]
    grounded: bool
