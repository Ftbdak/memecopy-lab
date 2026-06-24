# Backtesting Spec

> **STUB.** Owned by **PR-012 / PR-013** (Codex). Written when those PRs land.

Will define the historical data loader, the deterministic backtest engine, its
config (latency, slippage, fees, TP/SL, wallets) and outputs.

**Caveat carried from PR-000:** backtest is **approximate** because Jupiter has
no historical quote API and Birdeye historical granularity is tier-gated. The
**live paper trial (PR-024) is the primary edge evidence.** See README's
data-resolution caveat and `docs/data-feasibility-findings.md` (produced by
PR-000).
