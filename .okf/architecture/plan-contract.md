---
type: Concept
title: The plan contract
description: plan.yaml is the single artifact every role consumes, so it is validated hard at the boundary rather than trusted — and it ships wide, carrying fields for roles that do not exist yet.
resource: https://github.com/cybiqon-ai/longhaul/tree/main/src/longhaul/schema/plan.py
tags: [architecture, schema, contract, validation, implemented]
timestamp: 2026-08-30T00:00:00Z
---

# Overview

`.longhaul/plan.yaml` is what the Planner produces and what every other role
reads. The Reviewer diffs a change against a task's `acceptance_criteria`; the
DevOps role reads `profile`; the Proof gate reads `proof`. There is no second
source of truth about what the project is doing.

`schema/plan.py` is **built and tested**: `Plan`, `Milestone`, `Task` and `Proof`
dataclasses, a validator, and `json_schema()` which is handed to
`claude --json-schema` so the Planner's output is a validated contract rather
than parsed prose.

# Validated, not trusted

`Plan.from_dict` raises `PlanError` carrying **every** problem rather than the
first, because a plan is read once and executed for a fortnight. It rejects:

- a task with no `acceptance_criteria` — nothing downstream could check it, so
  the day could never honestly fail
- a dependency on a task scheduled on a **later** day
- a dependency cycle, found by depth-first search and reported as a path
- a dependency on a task id that does not exist
- duplicate task ids
- a day outside `1..target_days`
- an unknown `kind` or `risk`

The failure mode this prevents is specific: a plan that parses cleanly and is
self-contradictory does not fail at parse time, it fails on day 6, after five
days of work have been built on it.

# Wide schema, narrow build

`kind`, `surfaces`, `needs_human` and `proof` are in the schema now even though
the Designer, Issues agent and Proof gate that consume them are not built. The
alternative — a minimal schema — means every stored plan needs rewriting the
first time one of those roles lands. Ships wide once, rather than breaking later.

# See also

- [Agent roles](agent-roles.md) — the Planner, which produces this, and the roles that consume it
- [The Claude driver](driver.md) — `--json-schema` is what makes this a contract
- [Longhaul](/product/overview.md) — what exists and what does not
