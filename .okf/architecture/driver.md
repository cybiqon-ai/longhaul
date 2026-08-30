---
type: Concept
title: The Claude driver
description: Why Longhaul shells out to the user's own claude binary instead of embedding the Agent SDK — a licensing constraint, a cost constraint, and three capabilities that come free.
resource: https://github.com/cybiqon-ai/longhaul/tree/main/src/longhaul/driver
tags: [architecture, claude, subprocess, authentication, implemented]
timestamp: 2026-08-30T00:00:00Z
---

# Overview

`driver/base.py` defines `AgentRequest`, `AgentResult` and the `AgentDriver`
protocol. `driver/cli_driver.py` is the one implementation: it runs
`claude -p --output-format json` as a subprocess. **It is written and unit-tested
but nothing calls it yet** — there is no orchestrator.

# Why not the Agent SDK

**Licensing.** Anthropic does not permit a third-party product to offer claude.ai
login or subscription rate limits, including agents built on the Claude Agent
SDK. A tool that embedded the SDK and handled sign-in would be offside. Longhaul
never implements authentication: the user installs and authenticates Claude Code
themselves, and Longhaul reads `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`
from the environment.

The original spec's README promised *"sign in with your existing Claude Code
session"*. That promise had to be deleted.

**Cost.** A fourteen-day unattended run makes many long agent calls. Billed per
token against an API key that is an unpredictable bill for every user who tries
the project; run against a subscription they already pay for, the marginal cost
is zero. This is what makes an unattended multi-day run affordable at all.

# What comes free

- `--output-format json` returns `session_id` and `total_cost_usd` on every call,
  so the cost ledger and cross-day session resume are read rather than built.
- `--json-schema` makes an agent's output a validated contract instead of parsed
  prose — which is what lets `plan.yaml` be a contract at all.
- `--resume <session_id>` lets a retry carry the failure in context rather than
  re-reading the repository.

# Deliberate choices in the implementation

**Never `--dangerously-skip-permissions`.** It is defensible for a pipeline with
no write access to a codebase. A tool that edits and pushes an arbitrary user's
repository unattended is a different risk entirely. `CliDriver` passes `--permission-mode dontAsk` with an explicit
allowlist, and a unit test asserts the dangerous flag is absent from the argv.

**Empty stdout is a failure, not an empty result.** `_parse` returns `None` for
blank or unparseable output, and `run` converts that into `ok=False`. This is the
direct lesson of a four-night production outage in which an expired Claude
session was swallowed as success and a nightly pipeline ran empty.

**Auth failures raise rather than return.** `authentication_failed`,
`oauth_org_not_allowed` and `billing_error` raise `ClaudeAuthError`, so the
supervisor halts loudly instead of retrying against a logged-out CLI.

**Transient errors are named.** `rate_limit`, `overloaded` and `server_error` are
listed as `TRANSIENT` so a 429 does not consume a task's retry budget. **The
constant exists; nothing reads it yet.**

# See also

- [Longhaul](/product/overview.md) — what exists and what does not
- [Gates](gates.md) — what runs after the driver returns
