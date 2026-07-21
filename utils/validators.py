"""Small, dependency-free field validators shared across forms."""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,50}$")


def validate_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def validate_username(username: str) -> bool:
    return bool(_USERNAME_RE.match(username.strip()))


def validate_latitude(value: float) -> bool:
    return -90.0 <= value <= 90.0


def validate_longitude(value: float) -> bool:
    return -180.0 <= value <= 180.0


def validate_non_negative(value: float) -> bool:
    return value >= 0
