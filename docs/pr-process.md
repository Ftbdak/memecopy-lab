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
| No direct push to `main`              | **Convention (for now)** — see branch-protection note below |
| CI must pass to merge                 | **Convention (for now)** — CI runs on every PR (after PR-002); Owner merges only when green |
| PR uses the template / checklist      | **Convention** — template auto-populates; Owner verifies |
| "Claude AND Codex both approve"       | **Convention** — cannot be GitHub-enforced with one human; the Owner runs both reviews and merges only when both pass |
| Small, scoped PRs                     | **Convention** — enforced by discipline + review  |

Calling the cross-review "two required reviewers" in GitHub would be theater.
It is a discipline the Owner upholds, not a platform guarantee.

## Branch protection (the real config)

⚠️ **Branch protection / rulesets require GitHub Pro for a _private_ repo.** This
repo is private on a free plan, so platform-level protection is **not active
yet**. Until that changes, "no direct push to `main`" and "CI green to merge" are
**conventions the Owner upholds**, not platform guarantees.

To make them truly enforced, pick one:
- Upgrade the account to **GitHub Pro** (keeps the repo private), **or**
- Make the repo **public** (rulesets are free for public repos).

Once either is true, enable on `main`:
- Require a pull request before merging.
- Require status checks to pass (the `ci` workflow) — after PR-002 lands CI.
- Block force pushes & deletions.

The exact ruleset JSON is ready to apply via `gh api` the moment the plan allows
it — ask the Owner's assistant to enable it.

> The bootstrap/governance commit is seeded directly to `main` as the standard
> repo-initialization exception. Every change after it **should** go through a PR
> (convention) — and **must**, once protection is enabled.

## Roles in review

- **Codex opens a PR → Claude reviews.**
- **Claude opens a PR → Codex reviews.**
- Owner has final merge authority and is the tie-breaker.
- Use [`agent-prompts.md`](agent-prompts.md) verbatim for each task.
