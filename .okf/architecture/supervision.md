---
type: Concept
title: Supervision
description: Ceilings, loop detection, a lock and a kill switch — all enforced outside the agent, because a model told to respect a budget will report having respected the budget.
resource: https://github.com/cybiqon-ai/longhaul/tree/main/src/longhaul/core/supervisor.py
tags: [architecture, safety, budgets, scheduling, implemented]
timestamp: 2026-09-13T00:00:00Z
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

# A ceiling can only count what it sees

A call that times out or dies never emits a result event, so it never reports a
cost. It was recorded as $0.00: a thirty-minute design run, about $2.76, went
straight past every ceiling above. The driver now estimates a missing cost from
the partial stream's usage and the ledger marks it `cost_estimated`. The estimate
is a lower bound, and an unknown model is priced at the most expensive rate.

`limits.minutes_per_task` was in the same state until 2026-09-13 — documented
here and read by nothing, the real limit being a hard-coded thirty minutes.

Ceilings are also only **checked before a call**, never during one. The retry of
the day-3 design task was a single call that took the task to $9.19 against a $6
per-task ceiling. The next call was refused, correctly, but a call in flight is
never stopped for spend. The worst overshoot is one call's cost. A ceiling that
matters to the pound needs headroom of about one call.

# Retrying after a timeout

A timed-out attempt is retried in a **fresh session**, not resumed. Resuming
carries the whole conversation, which is re-read on every turn, and the files the
attempt wrote are in the worktree anyway. On day 3 the resumed retry cost $6.43
where a fresh design run had cost $2.48. The fresh session is told the previous
attempt ran out of time and to continue from the worktree. A gate or build
failure still resumes its session: that rejection is short, specific, and worth
keeping in context.

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
and must not page anyone.

# Killing the group, not the parent

`longhaul kill` signals the **process group**, and the lock records the pgid
alongside the pid for exactly that reason.

The first implementation signalled the pid only. Verified directly by spawning a
parent with a child and sending SIGTERM to the parent alone: **the child
survives**, reparented to init. For this tool that means an orphaned `claude -p`
still running, still spending, with no ceiling watching it — the ceilings above
can only account for spend they can see.

`kill` also refuses to clear the lock while the group still has members, even
when the recorded pid is gone. Clearing it then would invite a second run to
collide with the orphan.

# Config

`.longhaul/config.yml` is optional and its defaults are conservative.
`auto_merge` is `false` and there is no supported way to make it true. A test
asserts the shipped `templates/config.yml` matches the code's defaults, because a
template that has drifted from the code is documentation that lies.

# See also

- [The day loop](the-day-loop.md) — what supervision wraps
- [Notifications](notifications.md) — how a halt reaches a human
