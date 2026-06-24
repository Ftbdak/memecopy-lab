# Architecture

## Decisions

| Decision            | Choice & rationale                                                                 |
|---------------------|-------------------------------------------------------------------------------------|
| Language            | Python 3.11+ — one language across worker, backtest, API, dashboard.               |
| Packaging           | **Single installable package** `memecopy_lab` under `src/`. Not a JS-style `apps/ + packages/` monorepo — avoids Python import/namespace friction. |
| Dashboard (MVP)     | **Streamlit** — fastest path to a 24/7 view, all-Python. Next.js + FastAPI optional later if a polished public site is wanted. |
| API                 | FastAPI, **read-only**, introduced in Phase G.                                     |
| DB                  | SQLite first (zero-ops, file-based). PostgreSQL only if/when concurrency demands.  |
| Money               | `Decimal` everywhere. Never `float` for balances/prices/PnL.                        |
| Time                | UTC everywhere, timezone-aware.                                                     |
| Tooling             | ruff (lint+format), mypy (types), pytest (tests).                                   |

## Package layout

```
src/memecopy_lab/
  core/         # domain models, risk engine, backtest engine, scoring, exits
  adapters/
    solana_rpc/ # read-only RPC + WebSocket (logsSubscribe)
    jupiter/    # quote-only (no /swap build, no broadcast)
    birdeye/    # token market data
    helius/     # parsed transactions
  worker/       # wallet watcher + live paper engine
  api/          # FastAPI read-only endpoints
```

## Data flow (live paper)

```
wallet log stream  (one stream per wallet — logsSubscribe = 1 mention/sub)
   → swap parser            → TradeSignal
   → signal dedup + latency → drop duplicates, tag late (>30s)
   → risk engine            → RiskDecision (accept/reject + reason codes)
   → token safety / manip   → flags
   → Jupiter quote (paper)  → simulated fill price + slippage
   → paper broker           → PaperOrder / PaperPosition / PaperFill
   → storage (SQLite)
   → dashboard (Streamlit)
```

## Key external constraints

- **Solana `logsSubscribe`**: `mentions` accepts only **one** address per
  subscription → top-N wallets = N independent streams/workers.
- **Jupiter**: real-time quotes only — **no historical quote API**. Backtest
  fills are reconstructed from price data, not real past quotes.
- **Birdeye**: historical OHLCV granularity & coverage are tier-gated; fresh
  memecoins are often sparse in their first minutes — see PR-000 findings.

> These three constraints are validated naturally when the relevant adapters are
> built (PR-004/005/017) and when PR-000 measures real data resolution. They are
> taken as reasonable working assumptions now, not re-verified at bootstrap.
