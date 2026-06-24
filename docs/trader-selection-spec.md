# Trader Selection Spec

> **STUB.** Owned by **PR-006** (Claude). Written when PR-006 lands.

Will define the multi-metric scoring that replaces blind PnL ranking:
`profit_score`, `consistency_score`, `drawdown_penalty`, `copyability_score`,
`rug_exposure_penalty`, `latency_sensitivity_penalty` — plus the rule that a
wallet whose gains are unreproducible at ≤30s latency is **not** followed.
