# Anti-Rug / Anti-Manipulation Spec (v0)

> **Owner:** Claude (PR-009). **Reviewer:** Codex.
> This is the *specification* that PR-010 (Risk Engine) implements. It defines
> **what** each token-safety flag means and **what action** it forces. It does
> not contain implementation code.

## Purpose

Before any observed signal becomes a paper trade, the token it points to is run
through a battery of **safety checks**. Each check can raise one or more **risk
flags**. Each flag maps to an **action**. The risk engine aggregates these into
the `RiskDecision` (PR-003 / PR-010).

This filter exists for one reason: **a top wallet buying a token is not, by
itself, a reason for us to buy it.** The wallet may be the rug. The wallet may be
exit liquidity. The wallet may be uncopyable at our latency. Anti-rug is the line
between "copy blindly" and "copy only what survives scrutiny."

## Core principles

1. **Default posture: when in doubt, no trade.** Absence of data is *not*
   evidence of safety. `UNKNOWN_MARKET_DATA` is treated as risky, not neutral.
2. **Every flag is explainable.** Each produces a machine-readable reason code
   that lands in `RiskDecision.reason_codes`. No silent rejects (Constitution §4).
3. **Flags compose; the strictest action wins.** If any flag says `REJECT`, the
   trade is rejected regardless of other flags.
4. **All thresholds are defaults and are themselves parameters under test.**
   Memecoins are young and thin by nature; calibration happens in backtest
   (PR-013) and the live trial (PR-024), not by dogma. Defaults are deliberately
   conservative.
5. **No fabricated inputs.** If an adapter is disabled or returns nothing, the
   relevant check emits `UNKNOWN_*`, never a guessed value.

## Action vocabulary

| Action              | Meaning                                                                 |
|---------------------|-------------------------------------------------------------------------|
| `REJECT`            | No trade. Signal is dropped with reason code(s).                        |
| `REDUCE_SIZE`       | Allowed, but max position size is multiplied by a `size_factor < 1`.    |
| `ALLOW_WITH_WARNING`| Trade proceeds at normal size; flag is logged for the report/dashboard. |

When multiple actions apply, precedence is `REJECT` > `REDUCE_SIZE` >
`ALLOW_WITH_WARNING`. Multiple `REDUCE_SIZE` factors **multiply** (e.g. 0.5 × 0.5
= 0.25), then the result is clamped to the global 15% cap (Constitution §2). The
filter can only ever make a position *smaller*, never larger.

## Risk flags

Each flag below lists: what it detects, the data source, the default action, the
default threshold, and the rationale.

### 1. `LOW_LIQUIDITY`
- **Detects:** pool/quote liquidity too thin to enter and *exit* without
  destroying price.
- **Source:** Birdeye market data (PR-005); Jupiter quote price impact (PR-017).
- **Default action:** `REJECT` below a hard floor; `REDUCE_SIZE` in a soft band.
- **Default threshold:** reject if total liquidity `< $25k`; reduce size if
  `$25k–$100k`.
- **Why:** the most common way a "winning" copy turns into a loss is being unable
  to sell. Entry is easy; exit is where thin liquidity kills you.

### 2. `NEW_TOKEN_TOO_YOUNG`
- **Detects:** token / pool created very recently.
- **Source:** token mint creation time, pool creation time.
- **Default action:** `REDUCE_SIZE` (not auto-reject — memecoins are young by
  design).
- **Default threshold:** reduce size if pool age `< 30 min`; the exact floor is
  a tuned parameter (PR-013).
- **Why:** youngest tokens carry the highest rug rate, but a blanket reject would
  exclude the entire memecoin thesis. Calibrate, don't ban.

### 3. `UNKNOWN_MARKET_DATA`
- **Detects:** required market data (price, liquidity, holders) is missing or the
  adapter is disabled.
- **Source:** any required adapter returning nothing.
- **Default action:** `REJECT`.
- **Why:** **missing data is risky, not neutral.** We cannot size or exit a
  position we can't measure. This is the teeth behind "when in doubt, no trade."

### 4. `HIGH_PRICE_IMPACT`
- **Detects:** the quote for *our* intended size moves the price too much.
- **Source:** Jupiter quote `priceImpactPct` for our `amount` + `slippageBps`.
- **Default action:** `REDUCE_SIZE`, then `REJECT` if still over cap at minimum
  size.
- **Default threshold:** reduce above `1.5%` impact; reject above `3%` even at
  reduced size (ties to Constitution slippage cap).
- **Why:** price impact *is* our realized entry cost; high impact means the edge
  is eaten before the trade starts.

### 5. `HIGH_HOLDER_CONCENTRATION`
- **Detects:** a small number of wallets hold a large share of supply.
- **Source:** Birdeye / holder distribution.
- **Default action:** `REDUCE_SIZE`; `REJECT` at extreme concentration.
- **Default threshold:** reduce if top-10 holders `> 50%` of supply; reject if a
  single non-pool/non-burn wallet holds `> 25%`.
- **Why:** concentrated supply = one wallet can dump on us at will (classic
  rug / exit-liquidity setup).

### 6. `MINT_AUTHORITY_ACTIVE`
- **Detects:** the token's mint authority is not renounced (supply can be
  inflated).
- **Source:** on-chain mint account.
- **Default action:** `REJECT` (default), overridable to `REDUCE_SIZE` only by an
  explicit, documented config change.
- **Why:** an active mint authority can print unlimited tokens and dilute holders
  to zero. This is a canonical rug primitive.

### 7. `FREEZE_AUTHORITY_ACTIVE`
- **Detects:** the token's freeze authority is not renounced (your account can be
  frozen).
- **Source:** on-chain mint account.
- **Default action:** `REJECT`.
- **Why:** an active freeze authority can lock your ability to sell — you hold a
  token you can never exit. Even in paper mode we model this as unsellable, so it
  must reject.

### 8. `SUSPICIOUS_CREATOR`
- **Detects:** the deployer wallet is linked to prior rugs, or is freshly funded
  from a known rug-cluster funding source.
- **Source:** creator history; funding-source clustering (shares logic with the
  manipulation detector, PR-011).
- **Default action:** `REJECT` for known-rug creators; `REDUCE_SIZE` for
  thin/unknown-but-suspicious history.
- **Why:** serial ruggers reuse wallets and funding paths. Cheap, high-signal
  filter.

### 9. `POOL_TOO_NEW`
- **Detects:** the *liquidity pool* (as opposed to the mint) was created moments
  ago, or liquidity was just added.
- **Source:** pool creation / first-liquidity timestamp.
- **Default action:** `REDUCE_SIZE`; `REJECT` if pool age `< 2 min`.
- **Why:** the riskiest window for a rug-pull is immediately after pool creation,
  before any organic depth forms.

### 10. `NO_SELL_LIQUIDITY`
- **Detects:** a quote can be obtained to *buy* the token but **not** to sell it
  back (one-sided / honeypot-like behavior).
- **Source:** Jupiter quote attempt in the **reverse** direction (token → SOL/USDC)
  for a notional amount — quote-only, no transaction.
- **Default action:** `REJECT`.
- **Why:** this is the honeypot signature: easy in, impossible out. A buy-only
  token is a guaranteed loss. **Every prospective buy must pass a reverse-quote
  sellability probe.**

## Aggregation contract (input to PR-010)

The safety checker produces, for a `(signal, token)` pair:

```
TokenSafetyResult:
  flags: list[RiskFlag]            # e.g. [HIGH_PRICE_IMPACT, POOL_TOO_NEW]
  overall_action: REJECT | REDUCE_SIZE | ALLOW_WITH_WARNING
  size_factor: Decimal             # product of REDUCE_SIZE factors, in (0, 1]
  reason_codes: list[str]          # one per raised flag, machine-readable
  rug_score: int                   # 0–100, monotonic in severity (for scoring/reports)
  data_completeness: Decimal       # fraction of checks with real (non-unknown) data
```

Rules the risk engine (PR-010) must honor:
- `overall_action == REJECT` → `RiskDecision.accepted = False`, no order, ever.
- `REDUCE_SIZE` → `max_position_size = min(0.15 * balance, base_size * size_factor)`.
- Every raised flag contributes a reason code; `reason_codes` is never empty when
  a trade is rejected or resized.
- `data_completeness` below a floor (default `0.6`) itself triggers
  `UNKNOWN_MARKET_DATA` → `REJECT`.

## Defaults table (single source of truth)

| Flag                        | Reject threshold        | Reduce-size band         | Default action |
|-----------------------------|-------------------------|--------------------------|----------------|
| `LOW_LIQUIDITY`             | `< $25k`                | `$25k–$100k`             | REJECT/REDUCE  |
| `NEW_TOKEN_TOO_YOUNG`       | —                       | pool age `< 30 min`      | REDUCE         |
| `UNKNOWN_MARKET_DATA`       | any required field null | —                        | REJECT         |
| `HIGH_PRICE_IMPACT`         | `> 3%`                  | `1.5%–3%`                | REDUCE/REJECT  |
| `HIGH_HOLDER_CONCENTRATION` | single wallet `> 25%`   | top-10 `> 50%`           | REDUCE/REJECT  |
| `MINT_AUTHORITY_ACTIVE`     | active                  | —                        | REJECT         |
| `FREEZE_AUTHORITY_ACTIVE`   | active                  | —                        | REJECT         |
| `SUSPICIOUS_CREATOR`        | known rug creator       | thin/unknown history     | REJECT/REDUCE  |
| `POOL_TOO_NEW`              | pool age `< 2 min`      | `2–30 min`               | REJECT/REDUCE  |
| `NO_SELL_LIQUIDITY`         | reverse quote fails     | —                        | REJECT         |

> All numbers are **v0 defaults**, tuned in backtest (PR-013) and the live trial
> (PR-024). Changing any default requires a PR that edits this table — it is the
> single source of truth the implementation reads from.

## Out of scope for v0
- ML-based rug classifiers (framework-only in PR-011).
- Social/sentiment signals.
- Cross-chain checks (Solana only for now).

## Acceptance criteria (this PR)
- [x] Every flag is explained.
- [x] Every flag maps to reject / reduce-size / allow-with-warning.
- [x] Default posture is "when in doubt, no trade."
- [x] Aggregation contract for PR-010 is defined (flags → action → size_factor →
      reason codes).
- [x] A single defaults table is the source of truth.
- [x] No implementation code; no live-trading path introduced.
