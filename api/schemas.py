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

from typing import Optional

from pydantic import BaseModel, ConfigDict

from models.user import UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


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
