"""Core domain models for MemeCopy Lab.

All models are immutable (``frozen=True``) data containers. Business rules
(the 15% cap, risk gating, etc.) live in the engine layers (PR-010+); these
models only hold data and enforce structural invariants:

- every timestamp is timezone-aware UTC,
- every monetary/amount value is ``Decimal`` (never ``float``),
- fractions are in ``[0, 1]`` and integer scores in ``[0, 100]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from .constants import DEFAULT_COPY_LATENCY_SECONDS, MAX_POSITION_PCT
from .enums import (
    BacktestStatus,
    OrderStatus,
    PositionStatus,
    RiskAction,
    TradeSide,
)
from .validation import (
    ensure_fraction,
    ensure_non_negative,
    ensure_positive,
    ensure_score,
    ensure_unit_interval_exclusive_low,
    ensure_utc,
)


@dataclass(frozen=True, slots=True)
class Wallet:
    """A tracked on-chain wallet."""

    address: str
    chain: str = "solana"
    label: str | None = None
    first_seen_at: datetime | None = None
    is_blacklisted: bool = False

    def __post_init__(self) -> None:
        if not self.address:
            raise ValueError("Wallet.address must be non-empty")
        if self.first_seen_at is not None:
            ensure_utc(self.first_seen_at, "Wallet.first_seen_at")


@dataclass(frozen=True, slots=True)
class TraderProfile:
    """Scored performance profile of a tracked trader.

    Selection never uses raw PnL alone (Constitution §3); the scores below feed
    the trader-selection logic in PR-006.
    """

    wallet_address: str
    trade_count: int
    net_pnl_usd: Decimal
    win_rate: Decimal
    max_drawdown: Decimal
    computed_at: datetime
    profit_factor: Decimal | None = None
    avg_hold_seconds: Decimal | None = None
    median_realized_pnl_usd: Decimal | None = None
    copyability_score: Decimal | None = None
    rug_exposure_score: Decimal | None = None
    latency_sensitivity_score: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.wallet_address:
            raise ValueError("TraderProfile.wallet_address must be non-empty")
        if self.trade_count < 0:
            raise ValueError("TraderProfile.trade_count must be >= 0")
        ensure_fraction(self.win_rate, "TraderProfile.win_rate")
        ensure_fraction(self.max_drawdown, "TraderProfile.max_drawdown")
        ensure_utc(self.computed_at, "TraderProfile.computed_at")
        if self.profit_factor is not None:
            ensure_non_negative(self.profit_factor, "TraderProfile.profit_factor")
        if self.avg_hold_seconds is not None:
            ensure_non_negative(self.avg_hold_seconds, "TraderProfile.avg_hold_seconds")


@dataclass(frozen=True, slots=True)
class Token:
    """A token (memecoin or quote asset) the system may observe or trade."""

    mint: str
    decimals: int
    symbol: str | None = None
    created_at: datetime | None = None
    liquidity_usd: Decimal | None = None
    is_blacklisted: bool = False

    def __post_init__(self) -> None:
        if not self.mint:
            raise ValueError("Token.mint must be non-empty")
        if self.decimals < 0:
            raise ValueError("Token.decimals must be >= 0")
        if self.created_at is not None:
            ensure_utc(self.created_at, "Token.created_at")
        if self.liquidity_usd is not None:
            ensure_non_negative(self.liquidity_usd, "Token.liquidity_usd")


@dataclass(frozen=True, slots=True)
class ObservedTransaction:
    """A raw on-chain transaction observed for a tracked wallet, pre-parsing."""

    signature: str
    wallet_address: str
    block_time: datetime
    observed_at: datetime
    slot: int | None = None
    is_swap: bool = False
    program_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.signature:
            raise ValueError("ObservedTransaction.signature must be non-empty")
        if not self.wallet_address:
            raise ValueError("ObservedTransaction.wallet_address must be non-empty")
        ensure_utc(self.block_time, "ObservedTransaction.block_time")
        ensure_utc(self.observed_at, "ObservedTransaction.observed_at")


@dataclass(frozen=True, slots=True)
class TradeSignal:
    """A parsed BUY/SELL intent derived from an observed wallet transaction."""

    signal_id: str
    source_wallet: str
    token_mint: str
    side: TradeSide
    chain_tx_signature: str
    chain_tx_time: datetime
    detected_at: datetime
    source_amount_in: Decimal
    source_amount_out: Decimal
    confidence: Decimal
    parser_version: str

    def __post_init__(self) -> None:
        if not self.signal_id:
            raise ValueError("TradeSignal.signal_id must be non-empty")
        if not self.chain_tx_signature:
            raise ValueError("TradeSignal.chain_tx_signature must be non-empty")
        ensure_utc(self.chain_tx_time, "TradeSignal.chain_tx_time")
        ensure_utc(self.detected_at, "TradeSignal.detected_at")
        ensure_non_negative(self.source_amount_in, "TradeSignal.source_amount_in")
        ensure_non_negative(self.source_amount_out, "TradeSignal.source_amount_out")
        ensure_fraction(self.confidence, "TradeSignal.confidence")

    @property
    def detection_latency_seconds(self) -> Decimal:
        """Seconds between the on-chain trade and our detection of it."""
        delta = self.detected_at - self.chain_tx_time
        return Decimal(str(delta.total_seconds()))

    def is_late(self, max_latency_seconds: int = DEFAULT_COPY_LATENCY_SECONDS) -> bool:
        """Whether this signal arrived later than the copy-latency budget."""
        return self.detection_latency_seconds > Decimal(max_latency_seconds)


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """The risk/safety verdict for a signal.

    Aggregates the token-safety result (``docs/anti-rug-spec.md``) and portfolio
    limits into an accept/reject with explainable reason codes (Constitution §4).
    """

    accepted: bool
    action: RiskAction
    reason_codes: tuple[str, ...]
    max_position_size_usd: Decimal
    size_factor: Decimal
    rug_score: int
    manipulation_score: int
    data_completeness: Decimal
    created_at: datetime
    liquidity_score: Decimal | None = None

    def __post_init__(self) -> None:
        ensure_non_negative(
            self.max_position_size_usd, "RiskDecision.max_position_size_usd"
        )
        ensure_unit_interval_exclusive_low(self.size_factor, "RiskDecision.size_factor")
        ensure_score(self.rug_score, "RiskDecision.rug_score")
        ensure_score(self.manipulation_score, "RiskDecision.manipulation_score")
        ensure_fraction(self.data_completeness, "RiskDecision.data_completeness")
        ensure_utc(self.created_at, "RiskDecision.created_at")
        # Constitution §4: a rejection or a resize is never silent.
        if not self.accepted and not self.reason_codes:
            raise ValueError("RiskDecision: a rejected decision must have reason_codes")
        if self.action is RiskAction.REJECT and self.accepted:
            raise ValueError(
                "RiskDecision: action=REJECT is inconsistent with accepted=True"
            )
        if self.liquidity_score is not None:
            ensure_non_negative(self.liquidity_score, "RiskDecision.liquidity_score")


@dataclass(frozen=True, slots=True)
class PaperOrder:
    """A simulated order. Never submits a real transaction (Constitution §1)."""

    order_id: str
    signal_id: str
    token_mint: str
    side: TradeSide
    requested_amount: Decimal
    requested_notional_usd: Decimal
    max_slippage_bps: int
    created_at: datetime
    status: OrderStatus = OrderStatus.PENDING

    def __post_init__(self) -> None:
        if not self.order_id:
            raise ValueError("PaperOrder.order_id must be non-empty")
        ensure_positive(self.requested_amount, "PaperOrder.requested_amount")
        ensure_non_negative(
            self.requested_notional_usd, "PaperOrder.requested_notional_usd"
        )
        if self.max_slippage_bps < 0:
            raise ValueError("PaperOrder.max_slippage_bps must be >= 0")
        ensure_utc(self.created_at, "PaperOrder.created_at")


@dataclass(frozen=True, slots=True)
class PaperFill:
    """A simulated fill produced by the paper broker from a real quote."""

    fill_id: str
    order_id: str
    token_mint: str
    side: TradeSide
    price_usd: Decimal
    amount: Decimal
    quote_amount_usd: Decimal
    fee_usd: Decimal
    slippage_bps: int
    filled_at: datetime

    def __post_init__(self) -> None:
        if not self.fill_id:
            raise ValueError("PaperFill.fill_id must be non-empty")
        ensure_non_negative(self.price_usd, "PaperFill.price_usd")
        ensure_positive(self.amount, "PaperFill.amount")
        ensure_non_negative(self.quote_amount_usd, "PaperFill.quote_amount_usd")
        ensure_non_negative(self.fee_usd, "PaperFill.fee_usd")
        if self.slippage_bps < 0:
            raise ValueError("PaperFill.slippage_bps must be >= 0")
        ensure_utc(self.filled_at, "PaperFill.filled_at")


@dataclass(frozen=True, slots=True)
class PaperPosition:
    """An open or closed simulated position."""

    position_id: str
    token_mint: str
    source_wallet: str
    amount: Decimal
    avg_entry_price_usd: Decimal
    cost_basis_usd: Decimal
    opened_at: datetime
    status: PositionStatus = PositionStatus.OPEN
    realized_pnl_usd: Decimal = field(default_factory=lambda: Decimal(0))
    closed_at: datetime | None = None
    exit_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.position_id:
            raise ValueError("PaperPosition.position_id must be non-empty")
        ensure_non_negative(self.amount, "PaperPosition.amount")
        ensure_non_negative(
            self.avg_entry_price_usd, "PaperPosition.avg_entry_price_usd"
        )
        ensure_non_negative(self.cost_basis_usd, "PaperPosition.cost_basis_usd")
        ensure_utc(self.opened_at, "PaperPosition.opened_at")
        if self.closed_at is not None:
            ensure_utc(self.closed_at, "PaperPosition.closed_at")
        if self.status is PositionStatus.CLOSED and self.closed_at is None:
            raise ValueError("PaperPosition: a CLOSED position must have closed_at")

    def unrealized_pnl_usd(self, mark_price_usd: Decimal) -> Decimal:
        """Mark-to-market unrealized PnL at ``mark_price_usd`` per token."""
        ensure_non_negative(mark_price_usd, "mark_price_usd")
        return self.amount * mark_price_usd - self.cost_basis_usd


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """A point-in-time view of the paper portfolio."""

    snapshot_id: str
    taken_at: datetime
    cash_balance_usd: Decimal
    positions_value_usd: Decimal
    realized_pnl_usd: Decimal
    unrealized_pnl_usd: Decimal
    open_position_count: int
    day_start_equity_usd: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError("PortfolioSnapshot.snapshot_id must be non-empty")
        ensure_utc(self.taken_at, "PortfolioSnapshot.taken_at")
        ensure_non_negative(self.cash_balance_usd, "PortfolioSnapshot.cash_balance_usd")
        ensure_non_negative(
            self.positions_value_usd, "PortfolioSnapshot.positions_value_usd"
        )
        if self.open_position_count < 0:
            raise ValueError("PortfolioSnapshot.open_position_count must be >= 0")
        if self.day_start_equity_usd is not None:
            ensure_non_negative(
                self.day_start_equity_usd, "PortfolioSnapshot.day_start_equity_usd"
            )

    @property
    def equity_usd(self) -> Decimal:
        """Total equity: cash plus marked position value."""
        return self.cash_balance_usd + self.positions_value_usd

    @property
    def daily_drawdown(self) -> Decimal | None:
        """Fractional drawdown vs. the day's starting equity, if known."""
        if self.day_start_equity_usd is None or self.day_start_equity_usd == 0:
            return None
        drop = self.day_start_equity_usd - self.equity_usd
        if drop <= 0:
            return Decimal(0)
        return drop / self.day_start_equity_usd


@dataclass(frozen=True, slots=True)
class BacktestRun:
    """Configuration and results of a single backtest run.

    Results are approximate by design (no historical executable quotes — see
    ``docs/data-feasibility-findings.md``). Result fields stay ``None`` until the
    run completes.
    """

    run_id: str
    start_date: datetime
    end_date: datetime
    initial_balance_usd: Decimal
    wallets: tuple[str, ...]
    created_at: datetime
    max_position_pct: Decimal = MAX_POSITION_PCT
    latency_seconds: int = DEFAULT_COPY_LATENCY_SECONDS
    status: BacktestStatus = BacktestStatus.PENDING
    final_balance_usd: Decimal | None = None
    total_return: Decimal | None = None
    max_drawdown: Decimal | None = None
    win_rate: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("BacktestRun.run_id must be non-empty")
        ensure_utc(self.start_date, "BacktestRun.start_date")
        ensure_utc(self.end_date, "BacktestRun.end_date")
        ensure_utc(self.created_at, "BacktestRun.created_at")
        if self.end_date < self.start_date:
            raise ValueError("BacktestRun.end_date must be >= start_date")
        ensure_positive(self.initial_balance_usd, "BacktestRun.initial_balance_usd")
        ensure_fraction(self.max_position_pct, "BacktestRun.max_position_pct")
        if self.latency_seconds < 0:
            raise ValueError("BacktestRun.latency_seconds must be >= 0")
        if self.win_rate is not None:
            ensure_fraction(self.win_rate, "BacktestRun.win_rate")
        if self.max_drawdown is not None:
            ensure_fraction(self.max_drawdown, "BacktestRun.max_drawdown")
