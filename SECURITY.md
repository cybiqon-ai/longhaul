# Security policy

## Reporting a vulnerability

Email **pyguru123@gmail.com** with `[longhaul security]` in the subject. Please
do not open a public issue for a vulnerability.

You should get an acknowledgement within a week. If the issue is confirmed, the
fix and an advisory will be published together.

## Scope

Longhaul executes model-generated code, writes to your repository, and pushes to
your remote. The following are in scope and taken seriously:

- Anything that lets a target repository's contents (a `CLAUDE.md`, a hook, an
  MCP config, a task description) escalate Longhaul's permissions or exfiltrate
  credentials.
- A path by which the secret-scanning gate can be bypassed before a push.
- A path by which the cheat-detector gates can be silently disabled.
- Anything that causes `longhaul ui` to bind beyond `127.0.0.1` without the
  explicit flag, or to serve secrets to the browser.
- Auto-merge occurring without an explicit per-repo opt-in.

## Not in scope

- That Longhaul runs model-generated code at all. That is the product. It is why
  work happens in isolated worktrees, why auto-merge is off by default, and why
  CI is the source of truth rather than the agent's self-report.
- Cost overruns from your own ceiling configuration.
