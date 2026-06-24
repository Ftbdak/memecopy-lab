## Summary

## Scope

## Out of Scope

## Safety Checklist

- [ ] This PR does not add live trading.
- [ ] This PR does not load private keys.
- [ ] This PR does not sign transactions.
- [ ] This PR does not broadcast transactions.
- [ ] This PR does not add exchange write permissions.
- [ ] This PR does not bypass the risk engine.
- [ ] Max paper position size remains capped at 15%.
- [ ] All trade decisions are explainable with reason codes.
- [ ] Money uses Decimal; timestamps are UTC.
- [ ] Secrets are not committed.

## Tests

Commands run:

- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] `mypy`
- [ ] `pytest`

## Reviewer Notes

## Live Trading Risk

Answer clearly: **Does this PR introduce any path to real-money trading?**
