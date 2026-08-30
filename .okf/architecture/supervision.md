---
type: Concept
title: Supervision
description: Ceilings, loop detection, a lock and a kill switch — all enforced outside the agent, because a model told to respect a budget will report having respected the budget.
resource: https://github.com/cybiqon-ai/longhaul/tree/main/src/longhaul/core/supervisor.py
tags: [architecture, safety, budgets, scheduling, implemented]
timestamp: 2026-08-30T00:00:00Z
---

# Overview

**Built.** `core/supervisor.py`, `core/lock.py` and `schema/config.py`. This is
the role the original spec called out as the one people forget, and the one that
stops a runaway agent looping on the same broken test for six hours.

Everything is enforced by the orchestrator, never by asking the agent. A model
told to respect a budget produces a model that says it respected the budget.

# Ceilings

From `.longhaul/config.yml`, checked **before** any spend: project total, daily
total, per-task total, and the attempt budget. A ceiling reached sets the task to
`halted` and returns without calling the model at all — a test asserts the driver
is never invoked, because a ceiling that reports after the fact is not a ceiling.

`halted` is a new status, distinct from `failed`: failed is retryable, halted
needs a human to raise a ceiling or fix the cause. Neither is *settled*, so
dependents stay blocked.

# Loop detection, and the mistake in it

Each failure is fingerprinted — volatile fragments normalised away, then hashed —
and two identical consecutive failures halt the task before the attempt budget
runs out. Retrying a deterministic failure only spends money.

The first implementation normalised **every number**, which made
`expected 1, got 2` and `expected 3, got 4` the same fingerprint. An agent making
genuine progress across attempts would have been halted as though it were
looping. Bare digits are no longer stripped; durations, timestamps, temp paths,
addresses and git SHAs still are. **Over-normalising is worse than
under-normalising here: a missed loop costs one retry, a false loop costs the
task.**

# One run at a time

`core/lock.py` takes an exclusive `flock` on `.longhaul/lock`. A scheduled job
that can overlap itself will, the first time a run outlasts its interval, and two
orchestrators sharing one `state.json` and one set of worktrees corrupt both.
`flock` releases when the process dies, however it dies, which a PID file does
not.

An overlapping run **exits 0**, not 1: a skipped cron tick is normal operation
and must not page anyone. `longhaul kill` sends SIGTERM to the holder and clears
a stale lock left by a process that no longer exists.

# Config

`.longhaul/config.yml` is optional and its defaults are conservative.
`auto_merge` is `false` and there is no supported way to make it true. A test
asserts the shipped `templates/config.yml` matches the code's defaults, because a
template that has drifted from the code is documentation that lies.

# See also

- [The day loop](the-day-loop.md) — what supervision wraps
- [Notifications](notifications.md) — how a halt reaches a human
