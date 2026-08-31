---
type: Concept
title: The day loop
description: Pick one task, isolate it in a worktree, let the Coder implement it, gate the diff, build and test deterministically, record everything — and be safe to kill at any point.
resource: https://github.com/cybiqon-ai/longhaul/tree/main/src/longhaul/core/orchestrator.py
tags: [architecture, orchestration, state, idempotency, implemented]
timestamp: 2026-08-30T00:00:00Z
---

# Overview

`core/orchestrator.py` runs one task. It is **built**, and `longhaul run`
executes it, but it stops before git: nothing is committed or pushed yet.

```
next_task  → lowest day whose dependencies are settled
worktree   → .longhaul/worktrees/<id> on branch longhaul/<id>
Coder      → implements the task, writes tests
cheat gate → reads the diff BEFORE the build
DevOps     → install / lint / test / build, deterministically
state      → written atomically; ledger appended
```

# The two properties that matter

**Idempotent.** Running twice in a day must not do the work twice. A completed
task short-circuits.

**Resumable.** Killed at any point — a watchdog, SIGTERM, a closed laptop — the
next invocation continues from `state.json` rather than starting over. State is
written with a temp file and an atomic rename, because a half-written
`state.json` loses the whole project's memory, which is far worse than losing one
step. The ledger reader tolerates a torn final line for the same reason.

Without both, the thing is not safe to schedule, which is the entire point.

# The day's work has to land

Found by the first real multi-day run, and the most consequential bug in the
project so far.

Every task branched from the same starting commit, because nothing ever merged
back. Four tasks ran; each one rebuilt the Flutter scaffold from nothing; none
could see the day before it. Test counts went 3 → 12 → 53 → **3**. Every gate
passed, every build was green, and `longhaul status` reported `done: 2` while the
project had accumulated nothing at all.

The design assumed a human merging pull requests. With `auto_merge` off and no
remote configured, nothing ever landed — and what happens then was never
specified.

So a finished task now **fast-forwards the base branch** onto its own. The pull
request remains the review artefact and [rollback](operating.md) is how a day is
taken back. Fast-forward only: if the base moved independently, it refuses and
says so, because quietly resolving that is how work gets lost. It also refuses
over uncommitted changes and when the repository is on another branch, while
ignoring untracked files — `.longhaul/` is full of those during a run.

Worth naming what this was: a green status over work that was not accumulating.
That is the exact failure the gates exist to catch, one level up, in the
orchestrator itself.

# Decisions worth knowing

**The cheat gate runs before the build.** There is no point spending a build on a
diff that is already disqualified, and a test asserts the ordering — otherwise it
would silently drift to "after" and cost a build per rejected attempt.

**A task that changed nothing is a failure.** An agent that reports success while
producing an empty diff is the same failure shape as a suite that runs zero
tests.

**A parked task does not block later work.** `needs_human` tasks are parked
without spending anything, and `next_task` keeps scanning. One open question must
not stall a fortnight.

**A retry resumes the Coder's session** via `--resume` and carries the real build
output, not a summary — with an explicit instruction not to weaken the check that
caught it. Blind retries are how an agent burns a budget repeating the same
mistake.

**Failed is not settled.** Only `done` and `skipped` are terminal. `failed` is
retryable up to the attempt budget; `parked` waits for a human. Dependents of
either stay blocked.

# Not built

Git Ops (commit, push, PR), the Notifier, and the Supervisor's real ceilings —
cost, wall-clock, loop detection. `DEFAULT_MAX_ATTEMPTS = 3` is the only budget
enforced today.

# See also

- [Agent roles](agent-roles.md) — the twelve roles and which exist
- [The plan contract](plan-contract.md) — what the loop reads
- [Gates](gates.md) — the cheat detector this loop runs
