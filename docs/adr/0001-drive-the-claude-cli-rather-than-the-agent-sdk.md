# 1. Drive the Claude CLI rather than the Agent SDK

Date: 2026-08-30

## Status

Accepted.

## Context

Longhaul needs to invoke a coding agent many times a day, unattended, for weeks.
There were three options: embed the Claude Agent SDK and require an API key,
shell out to the `claude` binary the user already has, or support both from day
one behind an interface.

Two constraints decided it.

Cost: a fourteen-day unattended run makes many long agent calls. Billed per token
against an API key, that is a real and unpredictable bill for every user who tries
the project. Run against a subscription the user already pays for, the marginal
cost is zero.

Terms: Anthropic does not permit a third-party product to offer claude.ai login
or subscription rate limits. A tool that embedded the SDK and handled sign-in
would be offside. A tool that shells out to a binary the user installed and
authenticated themselves is not doing that at all.

## Decision

Longhaul drives the user's own `claude` binary as a subprocess and never
implements authentication. It reads `ANTHROPIC_API_KEY` or
`CLAUDE_CODE_OAUTH_TOKEN` from the environment and shells out.

`driver/base.py` defines an `AgentDriver` protocol so an SDK driver can be added
later without the orchestrator noticing.

## Consequences

Good: `--output-format json` returns `session_id` and `total_cost_usd` on every
call, so the cost ledger and cross-day session resume are free rather than
built. `--json-schema` turns an agent's output into a validated contract instead
of parsed prose. Users run on credentials they already have.

Bad: Longhaul requires Claude Code to be installed, which is a real install-time
dependency and a real support surface. Subprocess boundaries make streaming and
error attribution clumsier than in-process calls.

Sharp edge: an expired CLI session can fail in a way that reads as success. This
is the reason `doctor` round-trips a real prompt before every scheduled run, and
the reason `CliDriver` treats empty stdout as a failure rather than an empty
result.
