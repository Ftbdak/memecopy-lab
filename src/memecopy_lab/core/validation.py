"""Shared field validators for the domain models.

Kept deliberately small and dependency-free. Models call these from
``__post_init__`` to enforce the Constitution's invariants: timestamps are UTC,
money is non-negative where it must be, fractions live in ``[0, 1]``, and scores
live in ``[0, 100]``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal


def ensure_utc(value: datetime, field: str) -> None:
    """Require a timezone-aware datetime whose offset is exactly UTC."""
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be timezone-aware UTC, got {value!r}")


def ensure_non_negative(value: Decimal, field: str) -> None:
    """Require ``value >= 0``."""
    if value < 0:
        raise ValueError(f"{field} must be >= 0, got {value}")


def ensure_positive(value: Decimal, field: str) -> None:
    """Require ``value > 0``."""
    if value <= 0:
        raise ValueError(f"{field} must be > 0, got {value}")


def ensure_fraction(value: Decimal, field: str) -> None:
    """Require ``0 <= value <= 1``."""
    if not (Decimal(0) <= value <= Decimal(1)):
        raise ValueError(f"{field} must be within [0, 1], got {value}")


def ensure_unit_interval_exclusive_low(value: Decimal, field: str) -> None:
    """Require ``0 < value <= 1`` (e.g. a size-reduction factor)."""
    if not (Decimal(0) < value <= Decimal(1)):
        raise ValueError(f"{field} must be within (0, 1], got {value}")


def ensure_score(value: int, field: str) -> None:
    """Require an integer score within ``[0, 100]``."""
    if not (0 <= value <= 100):
        raise ValueError(f"{field} must be within [0, 100], got {value}")
