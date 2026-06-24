"""Constitutional risk limits, as typed constants.

These mirror the hard limits in ``docs/safety-constitution.md`` §2. The risk
engine (PR-010) reads from here so there is a single source of truth in code.
Changing any value here is a Constitution change and must go through a PR that
also updates the docs.
"""

from __future__ import annotations

from decimal import Decimal

# Max single position size, as a fraction of paper balance.
MAX_POSITION_PCT: Decimal = Decimal("0.15")

# Max exposure to a single token, as a fraction of paper balance.
MAX_TOKEN_EXPOSURE_PCT: Decimal = Decimal("0.15")

# Max simultaneous exposure to one source trader, as a fraction of balance.
MAX_TRADER_EXPOSURE_PCT: Decimal = Decimal("0.30")

# Max number of concurrently open paper positions.
MAX_OPEN_POSITIONS: int = 3

# Daily paper drawdown at which the engine stops opening new positions.
DAILY_MAX_DRAWDOWN_PCT: Decimal = Decimal("0.10")

# Default assumed copy latency (seconds). Signals older than this are "late".
DEFAULT_COPY_LATENCY_SECONDS: int = 30
