# Live Trading Ban

## The rule

MemeCopy Lab does **not** trade real money in v1. Full stop. This is not a
"feature we haven't built yet" — it is a deliberate constraint that the codebase
actively enforces.

## What is forbidden

- Loading or holding real private keys.
- Signing any blockchain transaction.
- Submitting / broadcasting any transaction to any network.
- Any exchange or DEX API call with **write** permission.
- Any code path, flag, env var, or CLI command that enables real execution
  (`live mode`, `force trade`, `buy now`, `sell now`, etc.).

## How it is enforced in code

- The only execution path is the **Paper Broker** (simulated fills).
- A `LiveBroker` interface may exist for future-proofing. Its only
  implementation raises `LiveBrokerNotImplementedError`. There is no second
  implementation in v1.
- Adapters that *could* sign/submit (e.g. Jupiter) are used in **quote-only**
  mode. The `/swap` (transaction-building) path is not wired in.
- The Solana adapter is **read-only**: `get_transaction`, `getSignaturesFor...`,
  `logsSubscribe`. No `sendTransaction`.

## Red-team obligation

PR-022 (Red-Team Safety Review) must actively try to find a path from any input
to real-money execution, and **prove none exists**. Any discovered path is a
blocking bug.

## The only gate that could ever change this

Discussing real money requires **all** of the following to be documented and
true (PR-025, Live Readiness Doc — documentation only, no code):

- [ ] 3-month backtest is positive (and not driven by 1–2 lucky trades).
- [ ] Live paper trading is positive over a meaningful window.
- [ ] Max drawdown is acceptable.
- [ ] Slippage sensitivity is acceptable (system survives +2% slippage).
- [ ] Rug filter demonstrably reduces bad trades.
- [ ] System ran many days without correctness bugs.
- [ ] A manual kill switch exists.
- [ ] A daily loss limit exists.
- [ ] A private-key handling plan exists and is reviewed.
- [ ] Legal / regulatory risk is understood and documented.

Even then, PR-025 only writes a **Go / No-Go** decision. It ships **no live
code**. Enabling live trading would be a separate, explicit, Owner-approved
project phase — out of scope for everything in this repo's current plan.
