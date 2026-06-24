"""Enumerations shared across the MemeCopy Lab domain models."""

from __future__ import annotations

from enum import Enum


class TradeSide(str, Enum):
    """Direction of an observed or simulated trade."""

    BUY = "BUY"
    SELL = "SELL"


class RiskAction(str, Enum):
    """Action the risk/safety layer takes on a signal.

    Mirrors the action vocabulary in ``docs/anti-rug-spec.md``. Precedence is
    ``REJECT`` > ``REDUCE_SIZE`` > ``ALLOW_WITH_WARNING``.
    """

    REJECT = "REJECT"
    REDUCE_SIZE = "REDUCE_SIZE"
    ALLOW_WITH_WARNING = "ALLOW_WITH_WARNING"


class OrderStatus(str, Enum):
    """Lifecycle of a paper order."""

    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class PositionStatus(str, Enum):
    """Lifecycle of a paper position."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class BacktestStatus(str, Enum):
    """Lifecycle of a backtest run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
