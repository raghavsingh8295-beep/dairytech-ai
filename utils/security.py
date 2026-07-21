"""Password hashing and strength validation.

Security-answer hashing reuses the same bcrypt functions after
normalization, so a leaked database never exposes recovery answers in
plain text either.
"""
from __future__ import annotations

from typing import Tuple

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def normalize_answer(answer: str) -> str:
    """Case/whitespace-insensitive normalization for security answers."""
    return answer.strip().lower()


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Return (is_valid, error_message). error_message is '' when valid."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number."
    return True, ""
