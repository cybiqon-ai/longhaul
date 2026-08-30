---
type: Product
title: Longhaul
description: An open-source tool that plans a project against a deadline and ships one day's coded, tested, committed work per day unattended — Cybiqon's first OSS project, and the fourth override of the no-new-products rule.
resource: https://github.com/cybiqon-ai/longhaul
tags: [product, open-source, agent, automation, claude, python, pre-alpha]
timestamp: 2026-08-30T00:00:00Z
---

# Overview

`oss/longhaul` — you give it a `target.md` and a number of days. A Planner turns
that into a dependency-ordered task graph with acceptance criteria per day. Then
once a day an Orchestrator picks the next eligible task and runs it through
Coder → DevOps → gates → proof → Reviewer → Git Ops, and pushes a PR.

Python 3.11+, MIT, stdlib-first with `pyyaml` as the only runtime dependency.
Destined for `github.com/cybiqon-ai/longhaul`; **not yet pushed, and no remote
is configured.**

# What actually exists

Created 30 Aug 2026. As of that date the repository contains:

- `plan.md` — the full design. This is the real specification.
- `src/longhaul/cli.py` — argparse surface. `doctor`, `gate`, `plan` and
  `simulate` work; the remaining seven subcommands are registered and exit 2
  with a pointer to `ROADMAP.md`.
- `src/longhaul/doctor.py` — preflight checks, including a real round-trip
  through the `claude` CLI.
- `src/longhaul/driver/` — the `AgentDriver` protocol and a working subprocess
  wrapper around `claude -p --output-format json`. **Never called by anything.**
- `src/longhaul/gates/cheat.py` — the cheat detector. Works, and is tested.
- `src/longhaul/schema/plan.py` — the `plan.yaml` contract and its validator.
- `src/longhaul/core/planner.py` + `roles/planner.md` — **the Planner, working**:
  it reads a target file, plans N days, and writes a validated `plan.yaml`.
- `src/longhaul/profiles/` — one profile, loaded and summarised into the
  Planner's prompt.
- `src/longhaul/core/{orchestrator,state,worktree,devops}.py` + `roles/coder.md`
  — **the day loop**: pick a task, isolate it in a git worktree, let the Coder
  implement it, gate the diff, build and test it, record state atomically.
  `longhaul run` and `longhaul status`.
- 87 passing tests, ruff clean, CI green.

**Nothing is committed or pushed yet.** The loop runs a task and stops before
git: Git Ops and the Notifier do not exist, and the Supervisor enforces only an
attempt budget — no cost or wall-clock ceilings, no loop detection. Eight of the
twelve roles in `plan.md` are still specifications.

# Why it is unusual

Two design bets separate it from the six or so similar projects in this space.

**The gates contain no model.** The dominant failure of a long-running coding
agent is not writing bad code — it is making the *gate* pass instead of making
the *code* work: deleting a failing test, marking it skipped, loosening the lint
config, editing the CI workflow that would have caught it. Each produces a green
run and a broken project. `gates/cheat.py` blocks those moves by reading the diff,
deterministically. This is ground rule 3 — *report a count, not a status* —
applied to an agent.

**Proof means the thing ran.** Tests passing is not evidence an app works. Each
task declares a proof artifact; for Android that is build → emulator → install →
screenshot → check the screenshot against the day's acceptance criteria.
`.longhaul/proof/day-NN/` is what makes "day 7 shipped" a picture rather than a
claim. **Not built.**

# Open exposure

**PyPI `longhaul` is taken** by an unrelated single-release MLX fine-tuning CLI
that also installs a `longhaul` command. The distribution name is therefore
`longhaul-ai` while the console script stays `longhaul` — a collision that only
bites a user who installs both, but it is real and it is not documented anywhere
except here and `plan.md`.

**`longhaul.dev` and `longhaul.sh` are both registered** (Cloudflare nameservers,
checked 30 Aug 2026). The original spec claimed `.dev` was clean; it is not.
`longhaul.build` and `longhaul.run` were free on that date.

**A kill criterion is set: a working `v0.1` by 30 Sep 2026**, or the project is
parked and marked deprecated rather than carried as an unfinished codebase.

# What it is not

- **Not a swarm.** One task at a time, deliberately.
- **Not working software.** See above. Any description of Longhaul in the present
  tense elsewhere is aspirational.
- **Not a Claude Code product.** Independent, MIT, unaffiliated with Anthropic.
  It may not carry Claude Code branding; "Powered by Claude" is permitted.
- **Not an SEO play.** GitHub README links are `nofollow`. This repository cannot
  pass PageRank and was not built to. It is a credibility artifact.

# See also

- [Agent roles](/architecture/agent-roles.md) — the twelve roles, and which are scoped for v0.1
- [Gates](/architecture/gates.md) — the one part of the design that runs today
- [The Claude driver](/architecture/driver.md) — why it shells out rather than embedding the SDK
