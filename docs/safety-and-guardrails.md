# Safety and guardrails

Longhaul pushes code, unattended, for days at a time. This document is the full
model behind the short version in the README.

## The one decision that matters

**Auto-merge to `main` is off by default and must be enabled per repository.**

Everything else here is a mitigation. This is the actual boundary between "an
agent opened a PR you'll read" and "an agent changed production while you slept."
If you turn it on, turn it on for one repository at a time, after you have
watched that repository run for a week.

## Isolation

Every task runs in its own `git worktree` under `.longhaul/worktrees/`, not on a
branch in your main checkout. A wedged day cannot leave your working tree in a
state you have to untangle by hand. Every completed day is a git tag, so
`longhaul rollback day-7` is a real operation rather than a manual reset.

## CI is the source of truth

A task is not done because the agent said the tests passed. It is done because CI
says so.

There is a trap here that Longhaul handles explicitly: **GitHub does not trigger
workflows on commits pushed with the default `GITHUB_TOKEN`.** A pipeline that
pushes with it gets a green project and a CI system that never ran — the failure
is invisible, because nothing reports an error. Longhaul pushes with a GitHub App
token or a PAT, and then *verifies that a CI run actually started* before it
waits on the result.

## The gates run before anything is pushed

Deterministic, diff-based, no model in the loop:

| Gate | Blocks |
|---|---|
| `cheat` | tests deleted or skipped, protected paths edited, errors swallowed, lint config loosened |
| `secrets` | anything matching a credential pattern, before it reaches a remote |
| `coverage` | a drop in coverage or test count (a ratchet, not a threshold) |
| `deps` | new dependencies with known advisories |

A gate that needs judgement is not a gate — that work belongs to the Reviewer
role, whose opinion is advisory and logged.

## Budgets are enforced outside the agent

Retry budgets, per-task and per-day cost ceilings, and wall-clock limits live in
the Supervisor. An agent is never asked to police its own spend. `total_cost_usd`
from every invocation is appended to `.longhaul/ledger.jsonl`, which is committed,
so the bill is auditable after the fact.

Retries feed the **actual error** back into the same session rather than
re-prompting blindly, and a bounded number of them end in a halt and an alert,
not in an unbounded loop.

## Escalation

These always go to a human, by design rather than by agent judgement:

- changes to auth, payment, or credential handling
- changes to CI workflows or to `.longhaul/config.yml`
- a task whose retry budget is exhausted
- an ambiguous requirement, or a decision that changes the architecture

Escalation **parks the task** and continues with unblocked work. One open
question should not stop a fourteen-day project.

## Authentication

Longhaul never handles your Claude login. You install and authenticate Claude
Code yourself; Longhaul reads `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`
from the environment and shells out.

`longhaul doctor` round-trips a real prompt through the CLI before every
scheduled run, because an expired session can fail in a way that reads as
success. Treating that as a hard failure is deliberate: the pattern has silently
killed a nightly pipeline for four consecutive nights in the wild.

## The dashboard

`longhaul ui` binds `127.0.0.1` only. It renders source, diffs and agent output,
so exposing it needs an explicit `--host` and prints a warning. Streamed output
is secret-redacted server-side before it reaches the browser.

## What Longhaul does not protect you from

It runs model-generated code. That is the product. Read the PRs.
