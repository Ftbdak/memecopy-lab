"""Unit tests for the core domain models (PR-003)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from memecopy_lab.core import (
    MAX_POSITION_PCT,
    BacktestRun,
    BacktestStatus,
    ObservedTransaction,
    OrderStatus,
    PaperFill,
    PaperOrder,
    PaperPosition,
    PortfolioSnapshot,
    PositionStatus,
    RiskAction,
    RiskDecision,
    Token,
    TraderProfile,
    TradeSide,
    TradeSignal,
    Wallet,
)

NOW = datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)


def test_wallet_minimal_and_utc_enforced() -> None:
    wallet = Wallet(address="abc")
    assert wallet.chain == "solana"
    assert not wallet.is_blacklisted

    with pytest.raises(ValueError, match="address must be non-empty"):
        Wallet(address="")
    with pytest.raises(ValueError, match="must be timezone-aware UTC"):
        Wallet(address="abc", first_seen_at=datetime(2026, 1, 1))  # naive


def test_non_utc_offset_rejected() -> None:
    eastern = timezone(timedelta(hours=-5))
    with pytest.raises(ValueError, match="must be timezone-aware UTC"):
        Wallet(address="abc", first_seen_at=datetime(2026, 1, 1, tzinfo=eastern))


def test_token_decimals_and_liquidity() -> None:
    token = Token(mint="mint1", decimals=6, liquidity_usd=Decimal("1234.5"))
    assert token.liquidity_usd == Decimal("1234.5")
    with pytest.raises(ValueError, match="decimals must be >= 0"):
        Token(mint="mint1", decimals=-1)
    with pytest.raises(ValueError, match="liquidity_usd must be >= 0"):
        Token(mint="mint1", decimals=6, liquidity_usd=Decimal("-1"))


def test_trader_profile_fraction_bounds() -> None:
    profile = TraderProfile(
        wallet_address="abc",
        trade_count=42,
        net_pnl_usd=Decimal("100"),
        win_rate=Decimal("0.55"),
        max_drawdown=Decimal("0.2"),
        computed_at=NOW,
    )
    assert profile.copyability_score is None
    with pytest.raises(ValueError, match="win_rate must be within"):
        TraderProfile(
            wallet_address="abc",
            trade_count=1,
            net_pnl_usd=Decimal("1"),
            win_rate=Decimal("1.5"),
            max_drawdown=Decimal("0.1"),
            computed_at=NOW,
        )


def test_trade_signal_latency_and_lateness() -> None:
    signal = TradeSignal(
        signal_id="s1",
        source_wallet="w1",
        token_mint="m1",
        side=TradeSide.BUY,
        chain_tx_signature="sig1",
        chain_tx_time=NOW,
        detected_at=NOW + timedelta(seconds=10),
        source_amount_in=Decimal("1"),
        source_amount_out=Decimal("2"),
        confidence=Decimal("0.9"),
        parser_version="v0",
    )
    assert signal.detection_latency_seconds == Decimal("10")
    assert not signal.is_late()
    assert signal.is_late(max_latency_seconds=5)


def test_trade_signal_confidence_bounds() -> None:
    with pytest.raises(ValueError, match="confidence must be within"):
        TradeSignal(
            signal_id="s1",
            source_wallet="w1",
            token_mint="m1",
            side=TradeSide.SELL,
            chain_tx_signature="sig1",
            chain_tx_time=NOW,
            detected_at=NOW,
            source_amount_in=Decimal("1"),
            source_amount_out=Decimal("2"),
            confidence=Decimal("1.1"),
            parser_version="v0",
        )


def _accepted_decision(**overrides: object) -> RiskDecision:
    base: dict[str, object] = dict(
        accepted=True,
        action=RiskAction.ALLOW_WITH_WARNING,
        reason_codes=(),
        max_position_size_usd=Decimal("150"),
        size_factor=Decimal("1"),
        rug_score=10,
        manipulation_score=5,
        data_completeness=Decimal("0.9"),
        created_at=NOW,
    )
    base.update(overrides)
    return RiskDecision(**base)  # type: ignore[arg-type]


def test_risk_decision_rejection_requires_reason_codes() -> None:
    with pytest.raises(ValueError, match="rejected decision must have reason_codes"):
        _accepted_decision(accepted=False, action=RiskAction.REJECT, reason_codes=())

    rejected = _accepted_decision(
        accepted=False, action=RiskAction.REJECT, reason_codes=("LOW_LIQUIDITY",)
    )
    assert not rejected.accepted
    assert rejected.reason_codes == ("LOW_LIQUIDITY",)


def test_risk_decision_reject_inconsistent_with_accepted() -> None:
    with pytest.raises(ValueError, match="REJECT is inconsistent"):
        _accepted_decision(action=RiskAction.REJECT, reason_codes=("X",))


def test_risk_decision_size_factor_and_scores() -> None:
    with pytest.raises(ValueError, match="size_factor must be within"):
        _accepted_decision(size_factor=Decimal("0"))
    with pytest.raises(ValueError, match="rug_score must be within"):
        _accepted_decision(rug_score=101)


def test_paper_order_validation() -> None:
    order = PaperOrder(
        order_id="o1",
        signal_id="s1",
        token_mint="m1",
        side=TradeSide.BUY,
        requested_amount=Decimal("10"),
        requested_notional_usd=Decimal("100"),
        max_slippage_bps=150,
        created_at=NOW,
    )
    assert order.status is OrderStatus.PENDING
    with pytest.raises(ValueError, match="requested_amount must be > 0"):
        PaperOrder(
            order_id="o1",
            signal_id="s1",
            token_mint="m1",
            side=TradeSide.BUY,
            requested_amount=Decimal("0"),
            requested_notional_usd=Decimal("100"),
            max_slippage_bps=150,
            created_at=NOW,
        )


def test_paper_fill_validation() -> None:
    fill = PaperFill(
        fill_id="f1",
        order_id="o1",
        token_mint="m1",
        side=TradeSide.BUY,
        price_usd=Decimal("0.5"),
        amount=Decimal("200"),
        quote_amount_usd=Decimal("100"),
        fee_usd=Decimal("0.3"),
        slippage_bps=120,
        filled_at=NOW,
    )
    assert fill.quote_amount_usd == Decimal("100")
    with pytest.raises(ValueError, match="amount must be > 0"):
        PaperFill(
            fill_id="f1",
            order_id="o1",
            token_mint="m1",
            side=TradeSide.BUY,
            price_usd=Decimal("0.5"),
            amount=Decimal("0"),
            quote_amount_usd=Decimal("100"),
            fee_usd=Decimal("0"),
            slippage_bps=0,
            filled_at=NOW,
        )


def test_paper_position_unrealized_pnl_and_closed_invariant() -> None:
    pos = PaperPosition(
        position_id="p1",
        token_mint="m1",
        source_wallet="w1",
        amount=Decimal("200"),
        avg_entry_price_usd=Decimal("0.5"),
        cost_basis_usd=Decimal("100"),
        opened_at=NOW,
    )
    # 200 tokens * $0.75 - $100 cost = $50 unrealized
    assert pos.unrealized_pnl_usd(Decimal("0.75")) == Decimal("50.00")
    assert pos.status is PositionStatus.OPEN

    with pytest.raises(ValueError, match="CLOSED position must have closed_at"):
        PaperPosition(
            position_id="p1",
            token_mint="m1",
            source_wallet="w1",
            amount=Decimal("0"),
            avg_entry_price_usd=Decimal("0.5"),
            cost_basis_usd=Decimal("100"),
            opened_at=NOW,
            status=PositionStatus.CLOSED,
        )


def test_portfolio_snapshot_equity_and_drawdown() -> None:
    snap = PortfolioSnapshot(
        snapshot_id="snap1",
        taken_at=NOW,
        cash_balance_usd=Decimal("800"),
        positions_value_usd=Decimal("150"),
        realized_pnl_usd=Decimal("-20"),
        unrealized_pnl_usd=Decimal("30"),
        open_position_count=2,
        day_start_equity_usd=Decimal("1000"),
    )
    assert snap.equity_usd == Decimal("950")
    # (1000 - 950) / 1000 = 0.05
    assert snap.daily_drawdown == Decimal("0.05")

    no_baseline = PortfolioSnapshot(
        snapshot_id="snap2",
        taken_at=NOW,
        cash_balance_usd=Decimal("1000"),
        positions_value_usd=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
        unrealized_pnl_usd=Decimal("0"),
        open_position_count=0,
    )
    assert no_baseline.daily_drawdown is None


def test_portfolio_snapshot_no_drawdown_when_up() -> None:
    snap = PortfolioSnapshot(
        snapshot_id="snap3",
        taken_at=NOW,
        cash_balance_usd=Decimal("1100"),
        positions_value_usd=Decimal("0"),
        realized_pnl_usd=Decimal("100"),
        unrealized_pnl_usd=Decimal("0"),
        open_position_count=0,
        day_start_equity_usd=Decimal("1000"),
    )
    assert snap.daily_drawdown == Decimal("0")


def test_backtest_run_defaults_and_date_order() -> None:
    run = BacktestRun(
        run_id="bt1",
        start_date=NOW - timedelta(days=90),
        end_date=NOW,
        initial_balance_usd=Decimal("1000"),
        wallets=("w1", "w2"),
        created_at=NOW,
    )
    assert run.max_position_pct == MAX_POSITION_PCT
    assert run.latency_seconds == 30
    assert run.status is BacktestStatus.PENDING
    assert run.final_balance_usd is None

    with pytest.raises(ValueError, match="end_date must be >= start_date"):
        BacktestRun(
            run_id="bt1",
            start_date=NOW,
            end_date=NOW - timedelta(days=1),
            initial_balance_usd=Decimal("1000"),
            wallets=("w1",),
            created_at=NOW,
        )


def test_observed_transaction_utc() -> None:
    tx = ObservedTransaction(
        signature="sig1",
        wallet_address="w1",
        block_time=NOW,
        observed_at=NOW + timedelta(seconds=2),
        is_swap=True,
        program_ids=("prog1",),
    )
    assert tx.is_swap
    with pytest.raises(ValueError, match="block_time must be timezone-aware UTC"):
        ObservedTransaction(
            signature="sig1",
            wallet_address="w1",
            block_time=datetime(2026, 1, 1),  # naive
            observed_at=NOW,
        )
