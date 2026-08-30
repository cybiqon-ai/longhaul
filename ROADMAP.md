# Roadmap

Sized for 1–2 focused hours a day. Each version ends at something demonstrable.
The full reasoning behind this ordering is in [`plan.md`](plan.md).

## v0.1 — it does one day ✅

`doctor` ✅ · `gate` ✅ · `init` ✅ · `plan` ✅ · `simulate` ✅ · `run` ✅ ·
`status` ✅ · `report` ✅

Planner ✅ → Coder ✅ → DevOps ✅ → Git Ops ✅. State, cost ledger, git worktrees, PR-only,
no auto-merge, Telegram notify-only, manual trigger.

The full plan schema and role registry ship **complete** in v0.1 even though half
the roles are unimplemented, so nothing downstream has to be rewritten later.

## v0.2 — it does many days unattended ✅

Supervisor ✅ — bounded retries with the real error fed back, loop detection,
cost ceilings, `flock` so a cron cannot overlap itself, and `longhaul kill`.
The cheat and secrets gates ✅. Resume after crash ✅. Notifier ✅ (Telegram).
Scheduling templates ✅ (cron, systemd, GitHub Actions, written by
`longhaul init --schedule`). `longhaul rollback` ✅ with per-task checkpoints.
`longhaul ui` ✅ — the report served live on `:4321` over SSE, localhost-only,
with credentials redacted before anything reaches a browser.

## v0.3 — it makes something you can look at

Designer and the day-1 design system. Asset pipeline with license provenance.
The Proof gate — build, emulator, screenshot, vision check. Project profiles.
The proof gallery in the dashboard.

## v0.4 — it runs the repo

Reviewer and ADRs. Scribe: README, CHANGELOG, `docs/devlog/day-NN.md`, and the
project's own knowledge bundle. Issues agent. Telegram commands and the
dashboard's Needs-you actions, over one shared command layer. Tagged releases
with build artifacts attached.

## v0.5 — it tells the truth about the deadline

Velocity tracking, re-planning, the weekly retro run, the editable plan view,
and `report --static` for publishing a dashboard to GitHub Pages.

## v1.0

Multi-repo workspaces (a frontend and a backend under one plan), pluggable
notifiers (Slack, Discord, webhook), and a plugin API for third-party roles and
gates.

---

## Not planned

- **Parallel task execution.** One task at a time is the design, not a limitation.
- **A hosted service.** Longhaul runs on your machine, against your repo, on your
  own Claude credentials.
- **Model abstraction over other providers.** The `AgentDriver` seam exists, but
  the project targets Claude Code and does not intend to chase parity elsewhere.
