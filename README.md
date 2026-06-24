# MemeCopy Lab

> **PAPER TRADING ONLY — NO LIVE TRADING. NO REAL MONEY. NO PRIVATE KEYS.**

A research / trading **lab** that asks a single, falsifiable question:

> If we observed the buy/sell actions of top Solana memecoin wallets and copied
> them in a **paper-trading** environment with a realistic delay (target ≤ 30s),
> would there have been a genuine, positive edge — both over the last 3 months
> and in live forward simulation?

This is **not** a money-making bot. The first version is a *3-month backtest +
live paper trading + anti-rug dashboard* research platform. A live-trading
adapter exists only as an interface and stays disabled until — and unless — the
research gates in [`docs/task-distribution.md`](docs/task-distribution.md) are
passed. See [`docs/live-trading-ban.md`](docs/live-trading-ban.md).

---

## Status

Bootstrapping. Governance is in place (this commit). Code starts at **PR-002**
(repo skeleton & CI). See the PR ladder in
[`docs/task-distribution.md`](docs/task-distribution.md).

## What it does (target v1)

1. Keeps a registry of top trader/wallets (selected by a multi-metric
   **copyability** score, never blind PnL).
2. Watches their on-chain buy/sell activity (Solana, read-only).
3. Parses transactions into BUY/SELL **signals**.
4. Runs anti-rug / anti-manipulation filters on the token.
5. If the **risk engine** approves, opens a **paper** trade
   (max position size = **15% of paper balance**).
6. Shows everything 24/7 on a dashboard: balance, open positions,
   realized/unrealized PnL, win rate, max drawdown, rejected trades + reasons,
   per-trader performance.
7. Runs a **≥ 3-month backtest** (approximate — see caveat below).
8. Runs **weeks of live paper trading** before the word "live" is even discussed.

## Tech stack (decided)

| Layer        | Choice                                  |
|--------------|------------------------------------------|
| Language     | Python 3.11+                             |
| Backend API  | FastAPI (later phases)                   |
| Worker       | Python async                             |
| Dashboard    | Streamlit (MVP) → optional Next.js later |
| DB           | SQLite (MVP) → PostgreSQL if needed      |
| Data         | pandas                                   |
| Tests        | pytest                                   |
| Lint/format  | ruff                                     |
| Type check   | mypy                                     |
| Packaging    | single installable package `memecopy_lab` |

### Layout

```
memecopy-lab/
  src/memecopy_lab/
    core/        # domain models, risk engine, backtest engine, scoring
    adapters/    # solana_rpc, jupiter (quote-only), birdeye, helius
    worker/      # wallet watcher + paper engine worker
    api/         # FastAPI read-only API
  scripts/       # backtest, run_worker, seed_wallets, export_report
  tests/         # unit, integration, fixtures
  docs/          # constitution, specs, process
  reports/       # backtest output (gitignored except summaries)
  .github/       # CI + PR template
```

> One installable Python package, **not** a JS-style `apps/ + packages/`
> monorepo. Avoids Python import/packaging friction.

## ⚠️ Data-resolution caveat (read this)

The central thesis depends on **30-second latency**. But:

- Jupiter has **no historical quote API** — quotes are real-time only.
- Backtest fills are therefore **reconstructed** from Birdeye OHLCV, whose finest
  affordable granularity over 3 months across many fresh memecoins may be
  ~1-minute candles, often sparse in exactly the first minutes that matter.
- **If the best resolution we can actually pull is 1-minute, we cannot
  distinguish entry at +0s from +30s, and "latency sensitivity" becomes
  unmeasurable in backtest.**

Therefore: the 3-month backtest is treated as **approximate**. The **live paper
trial** (real-time, real latency) is the **primary** edge evidence. **PR-000**
is a data-feasibility spike that must answer "can we reconstruct a fill at ~30s
resolution? yes/no" *before* we build the full backtest stack.

## Governance

- [Safety Constitution](docs/safety-constitution.md) — the hard rules.
- [Live Trading Ban](docs/live-trading-ban.md) — why & how live is locked.
- [PR Process](docs/pr-process.md) — how every change ships.
- [Task Distribution / PR Ladder](docs/task-distribution.md) — the full plan.
- [Architecture](docs/architecture.md) — stack & layout decisions.
- [Agent Prompts](docs/agent-prompts.md) — universal Claude & Codex prompts.

## Roles

- **Owner (Yusuf):** product / strategy. Decides chain, wallets, balance, risk
  appetite, what to show, and when "live" may be discussed.
- **Claude:** architect + risk-auditor + reviewer.
- **Codex:** implementer + test fixer.
- **Cross-review is a process convention** (one human, two AI tools) — see
  [`docs/pr-process.md`](docs/pr-process.md).
