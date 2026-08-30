---
type: Concept
title: Operating a project
description: init, report and rollback — getting a repository ready, seeing what happened, and undoing a day when it went wrong.
resource: https://github.com/cybiqon-ai/longhaul/tree/main/src/longhaul/core/init.py
tags: [architecture, cli, onboarding, reporting, rollback, implemented]
timestamp: 2026-08-30T00:00:00Z
---

# Overview

**Built.** The three commands that make v0.1 usable by someone other than its
author: `longhaul init`, `longhaul report`, `longhaul rollback`.

# init

Onboarding is where an unattended tool earns or loses trust. The failure it
avoids is discovering on day 4 that the toolchain was never installed, after
four days of work already exist on a branch — so `init` runs `doctor` before it
tells you to plan anything.

It writes `.longhaul/config.yml`, a `target.md` skeleton and the right
`.gitignore` lines, never overwrites an existing file, is idempotent, and
refuses an unknown profile **before writing anything** rather than leaving a
half-configured project.

The `.gitignore` block excludes only `worktrees/`, `runs/` and `lock`.
`plan.yaml`, `state.json` and `ledger.jsonl` are the audit trail and are meant
to be committed.

`--schedule cron|systemd|actions` writes a scheduling file to read before
installing. Each carries `flock`, a `timeout`, and a log directory created
before it is written to. The Actions template additionally warns that a push
with the default `GITHUB_TOKEN` means the repository's CI never runs.

# report

One self-contained HTML file with the CSS inlined and **zero external
resources**, so it opens from `file://`, from a CI artifact, or on a machine
that never ran the agent. Equally a live monitor and a post-mortem.

Two bugs found in it, both in the counting — the thing this project claims to
care about most:

1. It printed `tasks: 17` while the buckets summed to 16, because an
   `in_progress` task belonged to no bucket. **A summary whose parts do not add
   up to the whole is the failure this project is named for.** Every status is
   now reported, with a parametrised test asserting the counts reconcile.
2. It showed the reason a task failed or halted but **not** why one was parked —
   and a parked task is the one a human has to act on.

Everything is escaped; a test asserts a project name or an error containing
markup cannot inject into the page, because agent output reaches this file
verbatim.

# rollback

Every completed task leaves an annotated git tag, so *"put it back how it was
before day 7"* is a real operation rather than a manual reset performed at 2am.
Rolling back day N undoes N and everything after it.

**Destructive by definition, so the default describes and changes nothing** —
`--apply` is required. Rolled-back tasks return to `pending` with their
attempts, fingerprints, PR and commit references cleared, so the next run
genuinely retries them. Rolling back day 1 is refused: there is no checkpoint
before the first day, and silently discarding a whole repository is not
something a tool should do on a one-word command.

Tags are never moved. Re-running a finished day must not shift a checkpoint
someone may already have rolled back to.

# See also

- [The day loop](the-day-loop.md) — what produces the state these read
- [Supervision](supervision.md) — the ceilings `init` writes defaults for
- [Shipping](shipping.md) — where the checkpoints are created
