# PR-000 Data-Feasibility Findings

## Answer: NO

Can we reconstruct a fill at ~30s resolution?

**NO, not from this run.** The local adapters were disabled because
read-only API keys were not present, so no historical swaps or OHLCV
candles were pulled. No substitute or fabricated data was used.

The documented finest Birdeye OHLCV interval to test is `1m`, which is
already too coarse to distinguish a +0s fill from a +30s fill. This
must be confirmed with real keyed data before treating backtest fills
as anything more than approximate.

## Candidate Wallet

- Wallet: `86xCnPeV69n6t3DnyGvkKobf9FdN2H9oiVDdaMpo2MMY`
- Choice: Public seed wallet from the Helius enhanced-transactions address endpoint documentation. It is hardcoded only to validate read-only data feasibility; it is not treated as an endorsed top trader.

## Run Window

- Intended start UTC: `2026-03-26T19:12:46+00:00`
- Intended end UTC: `2026-06-24T19:12:46+00:00`
- Helius swaps observed: `0`
- Distinct non-quote token mints observed: `0`

## Reference Docs

- Helius enhanced transactions by address: https://www.helius.dev/docs/api-reference/enhanced-transactions/gettransactionsbyaddress
- Birdeye OHLCV: https://docs.birdeye.so/reference/get-defi-ohlcv

## Adapter Status

- `adapter disabled: missing HELIUS_API_KEY, BIRDEYE_API_KEY; add read-only keys to .env to run PR-000 without fabricated data`
- Required keys: `HELIUS_API_KEY`, `BIRDEYE_API_KEY`.

## Real Granularity

- Actual account-tier granularity was not measured because adapters were
  disabled.
- Birdeye's OHLCV endpoint documents `1m` as the finest listed interval.

## Coverage Gaps For Fresh Tokens

- Not measured in this local run because no keyed data was pulled.
- The PR-013 backtest must keep missing early token candles as `unknown`,
  never as inferred fills.

## Rate-Limit / Cost Reality

- Both data sources require read-only API keys.
- Birdeye OHLCV is capped at 1000 records per request, which means a
  90-day 1m analysis requires many requests per token.
- This spike intentionally exits instead of using fallback data when keys
  are missing.

## Implication For PR-013

- PR-013's 3-month backtest remains approximate.
- Without <=30s historical price/quote data, the backtest cannot measure
  the central latency question.
- The live paper trial remains the primary evidence for real 30s latency.

## Safety

- No live trading path was added.
- No private keys, transaction signing, transaction broadcasting, swaps,
  or exchange write APIs are introduced.
- Missing API keys disable the adapters; no data is fabricated.
