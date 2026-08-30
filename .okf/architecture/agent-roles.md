---
type: Concept
title: Agent roles
description: Twelve specified roles, four scoped for v0.1, none implemented — and the "narrow build, wide schema" decision that lets the later eight land without a rewrite.
resource: https://github.com/cybiqon-ai/longhaul/tree/main/src/longhaul/roles
tags: [architecture, agents, orchestration, specification, not-built]
timestamp: 2026-08-30T00:00:00Z
---

# Overview

Longhaul's design splits the work across twelve narrow roles rather than one
general agent. Each is a markdown prompt in `src/longhaul/roles/`, written in the
numbered-protocol style ("▶ STEP N", "run autonomously, there is nobody to
answer").

**One of the twelve is implemented: the Planner.** It reads a target file,
plans N days against a stack profile, and returns a validated plan — with
read-only tools, so a planning step can always be safely re-run. The other
eleven are specifications; this concept records the design, not the state.

# The roles

| Role | Responsibility | Scoped for |
|---|---|---|
| Planner **(built)** | target.md → dependency-ordered day-sized task graph with acceptance criteria | v0.1 |
| Orchestrator | Picks today's task, dispatches, decides retry vs escalate | v0.1 |
| Coder | Implements the task in an isolated worktree; writes code *and* tests | v0.1 |
| DevOps/QA | Build, lint, typecheck, test; reports structured failures | v0.1 |
| Git Ops | Worktree, conventional commit, push, PR, link issue | v0.1 |
| Notifier | Telegram digest, failure alerts, decision requests | v0.1 |
| Supervisor | Retry budget, loop detection, cost and wall-clock ceilings | v0.2 |
| Designer | Day-1 design system, then per-screen specs | v0.3 |
| Assets | Sprites, icons, audio, and `assets/CREDITS.md` provenance | v0.3 |
| Reviewer | Diff vs acceptance criteria; scope creep, security; writes ADRs | v0.4 |
| Scribe | README, CHANGELOG, devlog, and the project's own `.okf/` bundle | v0.4 |
| Issues | An issue per task, closed by its PR; bugs on failure | v0.4 |

# Narrow build, wide schema

The decision that shapes the sequencing: **only the v0.1 roles get built, but the
plan schema and the role registry ship complete from the first release.**

`plan.yaml` therefore carries `kind`, `surfaces`, `needs_human` and a `proof`
block from day one, even though the Designer, the Issues agent and the Proof gate
that consume them are months away. The alternative — a minimal schema now — means
a breaking rewrite of every stored plan the first time a Designer lands.

# The Supervisor is the one people forget

It wraps every agent call and is what stops a runaway loop burning tokens for six
hours on the same broken test. Bounded retries feed the **actual error** back into
the same session via `--resume` rather than re-prompting blindly, and ceilings are
enforced outside the agent rather than asked of it.

The pattern to generalise: wrap `claude -p` in `flock` and `timeout`, then
verify from a ledger that the run actually produced output. Trusting exit code 0
is how a scheduled agent runs empty for weeks without anyone noticing.

# Escalation parks, it does not halt

A single ambiguous decision must not stop a fourteen-day project. A task flagged
`needs_human` moves to a parked queue and the Orchestrator continues with
unblocked work; the resolution is recorded as an ADR.

# See also

- [Longhaul](/product/overview.md) — what exists and what does not
- [Gates](gates.md) — the deterministic checks that run between Coder and Git Ops
- [The Claude driver](driver.md) — how a role invocation actually reaches Claude
