# Task Distribution — PR Ladder

The full plan, as a sequence of small PRs. Each PR names an **Owner** (who
implements) and a **Reviewer** (who cross-reviews). See
[`pr-process.md`](pr-process.md).

> **Sequencing note:** Through PR-017 the system is *research infrastructure*.
> PR-018 starts live **paper** trading. PR-023 is the first real research
> verdict. The words "live trading" do not appear (as runnable code) anywhere
> before PR-025 — and PR-025 is documentation only.

## Legend
- **Owner** — writes the code / doc.
- **Reviewer** — cross-reviews before merge.
- Owner=Claude → architecture/risk/spec/review-heavy work.
- Owner=Codex → implementation/tests/refactor/CI.

---

## Phase 0 — Governance (done in bootstrap)

### PR-001 — Project Constitution & Safety Lock — **Owner: Claude**
Status: **seeded in bootstrap commit.** `safety-constitution.md`,
`live-trading-ban.md`, `pr-process.md`, PR template. (Already in `main`.)

---

## Phase A — Skeleton & feasibility

### PR-002 — Repo Skeleton & CI — Owner: **Codex** · Reviewer: Claude
Working, professional, empty skeleton.
- `pyproject.toml` (single package `memecopy_lab`, `src/` layout).
- `src/memecopy_lab/__init__.py` + submodule packages (`core`, `adapters`,
  `worker`, `api`) each with `__init__.py`.
- `.github/workflows/ci.yml`: `ruff check` · `ruff format --check` · `mypy` ·
  `pytest`.
- One trivial passing test so CI is green.
- **Acceptance:** `ruff`, `mypy`, `pytest` all pass; README says
  "paper trading only"; **zero** live-trading code.

### PR-000 — Data-Feasibility Spike — Owner: **Codex** · Reviewer: Claude
> Numbered 000 because it gates PR-012/013, but it runs right after the skeleton.
The single most important early experiment.
- Pick **one** candidate wallet.
- Pull ~3 months of its swaps (Helius / RPC).
- Pull the **finest price granularity actually available on our Birdeye tier**
  for the tokens it traded.
- **The only question to answer:** *Can we reconstruct a fill at ~30s resolution?
  Yes / No.* Document the real granularity (e.g. 1m candles?), coverage gaps for
  fresh tokens, and rate-limit/cost reality.
- Output: `docs/data-feasibility-findings.md`.
- **Gate:** if 30s-resolution reconstruction is impossible, the 3-month backtest
  is explicitly downgraded to "approximate" and the **live paper trial becomes
  the primary edge evidence** (this is already the framing — this spike confirms
  or refutes it with data).

### PR-003 — Domain Models — Owner: **Codex** · Reviewer: Claude
`Wallet`, `TraderProfile`, `Token`, `ObservedTransaction`, `TradeSignal`,
`RiskDecision`, `PaperOrder`, `PaperPosition`, `PaperFill`, `PortfolioSnapshot`,
`BacktestRun`.
- **Acceptance:** type-safe; unit tests; all timestamps **UTC**; money uses
  `Decimal`, never `float`.

---

## Phase B — Data ingestion & wallet tracking

### PR-004 — Solana RPC Read-Only Adapter — Owner: **Codex** · Reviewer: Claude
`get_transaction(signature)`, `get_signatures_for_address(...)`,
`subscribe_wallet_logs(address)`.
- `logsSubscribe` supports only **one** `mentions` address per subscription, so
  top-N wallets run as **separate streams/workers**.
- Forbidden: send / sign / private keys.
- **Acceptance:** mock RPC tests; rate-limit + backoff; WS reconnect on
  disconnect; read-only.

### PR-005 — Helius / Birdeye Optional Adapters — Owner: **Codex** · Reviewer: Claude
`HeliusParsedTransactionClient`, `BirdeyeTokenMarketDataClient`.
- Keys from `.env`; `.env.example` committed.
- No key → adapter **disabled**, not crashed.
- **Acceptance:** no real API calls in tests (mocks only).

### PR-006 — Wallet Registry & Trader Scoring v0 — Owner: **Claude** · Reviewer: Codex
`docs/trader-selection-spec.md`, `core/trader_score.py`.
Scores: `profit_score`, `consistency_score`, `drawdown_penalty`,
`copyability_score`, `rug_exposure_penalty`, `latency_sensitivity_penalty`.
- **Acceptance:** a wallet that mooned in 24h cannot be top-trader alone;
  minimum trade count required; suspiciously high PnL on few trades is flagged;
  no copyability score → not followed.

---

## Phase C — Transaction parser

### PR-007 — Swap Transaction Parser v0 — Owner: **Codex** · Reviewer: Claude
raw/parsed tx → `TradeSignal`. SOL/USDC→memecoin = BUY; memecoin→SOL/USDC = SELL.
- **Acceptance:** 20 fixture txns; unparseable → skip; low confidence → no
  signal; parser **never** executes a trade.

### PR-008 — Signal Deduplication & Latency Tracker — Owner: **Codex** · Reviewer: Claude
`SignalStore`, `DedupKey`, `LatencyMeasurement`
(`chain_tx_time`, `detected_at`, `parsed_at`, `paper_decision_at`,
`paper_fill_at`, `latency_seconds`).
- **Acceptance:** same signature → duplicate; >30s → "late"; late signals don't
  open trades by default (testable separately in backtest).

---

## Phase D — Anti-rug / anti-manipulation

### PR-009 — Token Safety Checks v0 (spec) — Owner: **Claude** · Reviewer: Codex
`docs/anti-rug-spec.md`. Flags: `LOW_LIQUIDITY`, `NEW_TOKEN_TOO_YOUNG`,
`UNKNOWN_MARKET_DATA`, `HIGH_PRICE_IMPACT`, `HIGH_HOLDER_CONCENTRATION`,
`MINT_AUTHORITY_ACTIVE`, `FREEZE_AUTHORITY_ACTIVE`, `SUSPICIOUS_CREATOR`,
`POOL_TOO_NEW`, `NO_SELL_LIQUIDITY`.
- **Acceptance:** each flag explained; each maps to reject / reduce size / allow
  with warning; default = when in doubt, no trade.

### PR-010 — Risk Engine — Owner: **Codex** · Reviewer: Claude
`evaluate_signal(signal, portfolio, token_data, trader_profile) -> RiskDecision`.
- **Acceptance:** every decision has reason codes; risk-bypass tests; the **15%**
  cap is locked by a unit test (balance 1000 → no single position > 150);
  rejected trade never becomes an order.

### PR-011 — Manipulation Pattern Detector v0 — Owner: **Claude** · Reviewer: Codex
Patterns: `PUMP_AFTER_WALLET_BUY`, `REPEATED_LOW_LIQUIDITY_WINS`,
`SAME_FUNDING_SOURCE_CLUSTER`, `BUY_THEN_PUBLIC_EXIT_PATTERN`,
`FAST_REVERSAL_PATTERN`, `COPY_TRADER_TRAP_PATTERN`.
- **Acceptance:** pattern interface; score 0–100; high score → reject or reduce;
  every pattern explainable. (Framework first; full detection can iterate.)

---

## Phase E — Backtesting *(approximate — see data caveat & PR-000)*

### PR-012 — Historical Data Loader — Owner: **Codex** · Reviewer: Claude
≥3 months of wallet tx history + token market data; slippage simulation;
quote approximation where no snapshot exists.
- **Acceptance:** date range per wallet list; rate-limit safe; missing data →
  `unknown`; **no fabricated fills**.

### PR-013 — Backtest Engine v0 — Owner: **Codex** · Reviewer: Claude
Config: `start/end`, `initial_balance`, `max_position_pct=0.15`,
`latency_seconds=30`, `slippage_model`, `fee_model`, TP/SL rules, `wallets`.
Output: final balance, total return, max drawdown, win rate, profit factor,
avg/median/best/worst trade, rejected count, rug-filter-saved losses.
- **Acceptance:** deterministic; JSON/CSV export; small fixture dataset test.

### PR-014 — Exit Strategy Simulator — Owner: **Claude** · Reviewer: Codex
TP/SL variants, trailing stop, time stops, lead-trader-sell follow, partial TP.
- **Acceptance:** ≥5 exit strategies backtestable; config-driven;
  lead-trader-exit tested separately; best strategy not chosen by overfit.

### PR-015 — Backtest Report Generator — Owner: **Codex** · Reviewer: Claude
`summary.md`, `trades.csv`, `rejected_trades.csv`, `equity_curve.csv`,
`wallet_performance.csv`, `token_risk_report.csv`.
- **Acceptance:** which wallet earned/lost; rug-filter saves; 30s-latency effect;
  15% sizing effect; slippage sensitivity — all in the report.

---

## Phase F — Live paper trading simulation

### PR-016 — Paper Broker — Owner: **Codex** · Reviewer: Claude
`open_position`, `close_position`, `mark_to_market`, `get_portfolio`.
- **Acceptance:** no tx submit; realistic slippage fills; fees deducted; correct
  PnL; size can't exceed 15%.

### PR-017 — Jupiter Quote Adapter (paper fills) — Owner: **Codex** · Reviewer: Claude
Quote via `inputMint`/`outputMint`/`amount`/`slippageBps`. **Quote-only.**
- Forbidden: `/swap` build/sign/broadcast.
- **Acceptance:** no quote → reject; price impact & quote latency logged;
  slippage cap exceeded → no trade.

### PR-018 — Live Paper Worker — Owner: **Codex** · Reviewer: Claude
Flow: wallet stream → parser → dedup → risk → quote → paper broker → storage →
dashboard.
- **Acceptance:** resumes after restart from DB; no duplicate trades; reads open
  positions on crash; every decision logged; **paper mode only**.

---

## Phase G — Dashboard

### PR-019 — Backend API (read-only) — Owner: **Codex** · Reviewer: Claude
`/health`, `/portfolio`, `/positions`, `/trades`, `/signals`, `/risk-decisions`,
`/wallets`, `/backtests`, `/metrics`.
- **Acceptance:** simple auth; not public without token; **read-only**; no
  trade-triggering endpoint.

### PR-020 — Dashboard v0 — Owner: **Codex** · Reviewer: Claude
Pages: Overview, Open Positions, Closed Trades, Rejected Signals, Wallet
Leaderboard, Token Risk, Backtest Reports, System Health.
- **Acceptance:** mobile-readable; auto-refresh; every value tagged **PAPER**;
  persistent red banner "No live trading enabled."

---

## Phase H — Observability & quality

### PR-021 — Logging, Metrics, Alerts — Owner: **Codex** · Reviewer: Claude
`signals_detected_total`, `signals_rejected_total`, `paper_trades_opened_total`,
`avg_detection_latency`, `avg_quote_latency`, `worker_uptime`, `rpc_errors`,
`api_errors`.
- **Acceptance:** structured logs; correct levels; visible in System Health;
  worker death detectable from logs.

### PR-022 — Red-Team Safety Review — Owner: **Claude** · Reviewer: Codex
Attacks: fake/duplicate/late signal, oversized trade, unknown token, low
liquidity, missing data, RPC replay, malformed tx, wrong decimals, negative
balance, PnL bug, **live-trading bypass attempt**.
- **Acceptance:** all in tests; any bypass → fix PR; **prove no path to live**.

### PR-023 — 3-Month Backtest Run — Owner: **Claude + Codex** · Reviewer: Owner
`reports/backtest_3m_v1/{summary.md,trades.csv,equity_curve.csv,rejected.csv}`.
Metrics: total return, max DD, Sharpe-like, profit factor, win rate, median PnL,
worst/best 5, latency & slippage sensitivity, wallet-by-wallet.
- **Gate (NO-GO if any):** result negative · profit from 1–2 outlier trades ·
  max DD too large · system flips negative at +2% slippage · rug filter helps
  when off but hurts when on (→ redesign risk).

### PR-024 — 2-Week Live Paper Trial — Owner: **Codex** · Reviewer: Claude
Min 14 days (prefer 30). The **primary edge evidence**.
- **Acceptance:** 24/7 worker; stable dashboard; PnL report; backtest-vs-live
  comparison; verify real latency <30s; list missed trades.

---

## Phase I — Live readiness (still NO live code)

### PR-025 — Live Readiness Document — Owner: **Claude** · Reviewer: Codex
Documentation **only**. Answers the gate checklist in
[`live-trading-ban.md`](live-trading-ban.md) and records a **Go / No-Go**.
- **Acceptance:** no live code; decision written down.

---

## Merge order

```
PR-001 → PR-002 → PR-000 → PR-003 → PR-004 → PR-005 → PR-006 → PR-007 →
PR-008 → PR-009 → PR-010 → PR-011 → PR-012 → PR-013 → PR-014 → PR-015 →
PR-016 → PR-017 → PR-018 → PR-019 → PR-020 → PR-021 → PR-022 → PR-023 →
PR-024 → PR-025
```

## Success / failure criteria

**Success:** 3-month backtest positive · live paper positive · slippage-robust ·
not dependent on one wallet · rug filter genuinely reduces bad trades ·
acceptable max DD · stable dashboard · worker self-recovers · all decisions
explainable · no accidental door to live trading.

**Failure (still valuable knowledge):** profit from one lucky trade · 30s
latency kills the edge · slippage flips it negative · top traders aren't
copyable · rug/manipulation filters too noisy · live results diverge wildly from
backtest.

> A negative result is a **legitimate, useful outcome.** The point is to learn
> whether the edge exists — not to force a bot into existence.
