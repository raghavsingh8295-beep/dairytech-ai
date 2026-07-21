"""Shared base exception for expected, user-facing business-rule failures.

Controllers raise `AppError` subclasses deliberately for invalid input,
permission denials, or "not found" cases — these are normal outcomes, not
bugs. `get_db_session` logs them at WARNING with no stack trace; anything
else it treats as an unexpected error and logs at ERROR with a traceback.
"""
from __future__ import annotations


class AppError(Exception):
    """Base class for all expected, user-facing controller-layer errors."""
