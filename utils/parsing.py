"""Shared form-field parsing for CustomTkinter dialogs.

Centralizing this means every date/number field in every module's form
gets the same error message format and the same empty-means-None handling,
instead of each dialog reimplementing its own try/except ValueError.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from utils.exceptions import AppError


def parse_optional_float(raw: str, field_label: str) -> Optional[float]:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise AppError(f"{field_label} must be a number.") from exc


def parse_optional_date(raw: str, field_label: str) -> Optional[date]:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise AppError(f"{field_label} must be in YYYY-MM-DD format.") from exc
