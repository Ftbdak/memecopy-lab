# PR Process

Every change ships as a small, reviewed PR. No exceptions, no direct pushes to
`main`.

## The six-step loop (every PR)

### 1. Plan
Before opening a PR, the owner writes a short plan (in the issue or PR
description):

```
Goal:
Scope:
Out of scope:
Files to touch:
Files that must NOT be touched:
Tests:
Safety risks:
Acceptance criteria:
```

### 2. Implementation
- Small commits.
- No large refactors.
- No scope creep.
- No live trading. No secrets.

### 3. Self-check
Owner runs locally before requesting review:

```bash
ruff check .
ruff format --check .
mypy .
pytest
```

### 4. Cross-review
The *other* agent reviews. Review focuses on:

```
Correctness · Tests · Risk bypass · Live-trading exposure · Secrets ·
Latency assumptions · PnL math · Position sizing · Error handling
```

### 5. Fix
Owner addresses review comments.

### 6. Merge gate
Merge only when:

- ✅ CI green *(enforced by branch protection)*.
- ✅ Reviewer approved.
- ✅ PR Safety Checklist fully checked.
- ✅ No live-trading path introduced.
- ✅ Docs updated if behavior changed.
- ✅ Tests present.

## Enforced vs. convention — be honest

This project is **one human (Owner) driving two AI tools (Claude + Codex)**. So:

| Rule                                  | Status                                            |
|---------------------------------------|---------------------------------------------------|
| No direct push to `main`              | **Enforced** — GitHub branch protection ruleset   |
| CI must pass to merge                 | **Enforced** — required status check *(after PR-002 establishes CI)* |
| PR uses the template / checklist      | **Convention** — template auto-populates; Owner verifies |
| "Claude AND Codex both approve"       | **Convention** — cannot be GitHub-enforced with one human; the Owner runs both reviews and merges only when both pass |
| Small, scoped PRs                     | **Convention** — enforced by discipline + review  |

Calling the cross-review "two required reviewers" in GitHub would be theater.
It is a discipline the Owner upholds, not a platform guarantee.

## Branch protection (the real config)

`main` ruleset:
- Require a pull request before merging.
- Require status checks to pass (the `ci` workflow) — enabled once PR-002 lands
  a real CI workflow.
- Block force pushes & deletions.

> The bootstrap/governance commit (this one) is seeded directly to `main` as the
> standard repo-initialization exception. Every change after it goes through a PR.

## Roles in review

- **Codex opens a PR → Claude reviews.**
- **Claude opens a PR → Codex reviews.**
- Owner has final merge authority and is the tie-breaker.
- Use [`agent-prompts.md`](agent-prompts.md) verbatim for each task.
