---
type: Concept
title: Shipping — commit, push, and proving CI ran
description: Git Ops is deterministic, auto-merge is off, and the one thing it checks that most pipelines get silently wrong is whether a CI run actually started.
resource: https://github.com/cybiqon-ai/longhaul/tree/main/src/longhaul/core/gitops.py
tags: [architecture, git, github, ci, safety, implemented]
timestamp: 2026-08-30T00:00:00Z
---

# Overview

`core/gitops.py` and `integrations/github.py` are **built**. After the gates and
the build pass, the day's work is committed with a conventional message, pushed,
and a pull request is opened. **Auto-merge does not exist and is not planned as a
default** — Longhaul opens PRs and waits.

The GitHub client is stdlib `urllib`: no `requests`, no `gh` CLI. This runs
unattended on machines the project does not control, and every dependency is
something that can break there.

# The check most pipelines get wrong

**GitHub does not trigger workflows on commits pushed with the default
`GITHUB_TOKEN`.** A pipeline that pushes with it gets green pull requests and a
CI system that never ran — no error, no warning, nothing to notice. "CI is the
source of truth" then quietly means nothing checked anything.

So `verify_ci_started` asks, every time, whether a workflow run exists for the
SHA just pushed, and treats absence as a **failure with a named cause** rather
than as silence. If the repository genuinely has no workflows it says that
instead — the two cases are different and are reported differently.

`wait_for_ci` additionally returns **how many jobs ran**, because a run can
conclude `success` having executed nothing. That is what an unparseable workflow
file looks like from the outside, and it is not hypothetical: it happened to this
repository on its first push.

# Deterministic, like DevOps

A conventional commit message is derivable from the task and its acceptance
criteria. Asking a model to write one spends money to produce something less
consistent, so `commit_message` builds it: a `type(task-id): title` subject
capped at 72 characters, the day, the acceptance criteria the change will be
judged against, and a note of which gates ran before the commit was made.

# Credentials never reach an error string

`parse_remote` redacts `user:token@host` before putting a URL into an exception.
Error strings reach logs, PR bodies and Telegram.

The test that covers this was originally written as
`assert "ghp_" not in msg or "example.com" in msg`, which passes on its second
clause while the token is echoed in full — a test with an `or` in its assertion
usually asserts nothing. Both the test and the missing redaction were fixed
together.

# Not built

Linking a PR to an issue, labels and milestones, releases with artifacts, and
any merge behaviour at all.

# See also

- [The day loop](the-day-loop.md) — what runs before this
- [Gates](gates.md) — the cheat and secrets gates, which must pass first
