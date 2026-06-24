# Safety Constitution

These rules are the **constitution** of MemeCopy Lab. They override convenience,
speed, and any individual PR's goals. A PR that violates any hard rule does not
merge — even if everything else is perfect.

## 1. Live trading is banned (hard rule)

In all v1 versions:

- **No** real private keys.
- **No** real swap transaction submission / broadcast.
- **No** transaction signing.
- **No** withdrawals.
- **No** exchange API write permissions.
- **No** `buy now` / `sell now` / `force trade` / `live mode` commands.

A live execution **interface** may exist for future-proofing, but its default
(and only) implementation must raise:

```
LiveBrokerNotImplementedError
```

See [`live-trading-ban.md`](live-trading-ban.md) for the full rationale and the
gate that would ever change this.

## 2. Risk limits (apply even in paper mode)

| Limit                                        | Value (initial)        |
|----------------------------------------------|------------------------|
| Max single position                          | **15%** of paper balance |
| Max exposure to a single token               | **15%**                |
| Max simultaneous exposure to one trader      | **30%**                |
| Max concurrent open positions                | **3**                  |
| Daily max paper drawdown (then stop opening) | **10%**                |
| Max assumed slippage per trade               | **1.5%–3%**            |

- Low liquidity → no trade.
- Token too young → no trade *(threshold is itself a tested parameter — memecoins
  are young by nature, so this is calibrated, not dogmatic)*.
- Bad rug score → no trade.
- **Every rejection logs a reason code.** No silent rejects.

These numbers are **defaults**, changeable only by the Owner and only via a PR
that updates this document.

## 3. No blind "top 5" copying

Top traders are **never** selected by raw PnL alone. Selection uses:

- Net PnL, win rate, profit factor, max drawdown
- Average hold time, median realized PnL
- Liquidity-adjusted PnL
- **Copyability score** (could *we* have copied this at ≤30s latency?)
- Insider / rug exposure score
- Post-trade performance at +30s, +1m, +5m, +15m

A wallet whose gains are unreproducible at our latency is **not** followed.
See [`trader-selection-spec.md`](trader-selection-spec.md).

## 4. Explainability

Every trade decision — accept *or* reject — must produce machine-readable
**reason codes**. "The model said so" is not acceptable. A `RiskDecision` with
no reasons is a bug.

## 5. Secrets

- No secrets, keys, or tokens committed. Ever.
- All credentials via `.env`, with a committed `.env.example`.
- Missing optional API key → the adapter is **disabled**, the system does not
  crash and never invents data.

## 6. Determinism & honesty in research

- The backtest engine is **deterministic**: same input → same output.
- Missing data is marked `unknown`. **No fabricated fills.**
- Results are reported faithfully, including negative ones. A negative result is
  a valid, valuable outcome (see [`task-distribution.md`](task-distribution.md)
  success criteria).

## 7. Process gates (see `pr-process.md`)

- No direct push to `main` *(enforced via branch protection)*.
- CI green required to merge *(enforced)*.
- PR Safety Checklist fully checked *(convention + template)*.
- Cross-review before merge *(convention — one human, two AI tools)*.
- Small PRs. No scope creep. No "while I'm here" refactors.
