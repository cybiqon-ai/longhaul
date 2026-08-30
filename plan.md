# Longhaul — Cybiqon's first open-source project

## Context

`oss/longhaul/spec.md` is a pasted planning transcript, not a repo — no code, no
schemas, no license, and its README draft contains two claims that are false.
This plan turns it into a real, buildable OSS project.

**What Longhaul is:** you give it a target file and a deadline in days. It plans
the whole project, then every day it designs, writes, builds, tests, documents,
commits and pushes one day's worth of work — and only wakes you when a human is
genuinely needed. The reference target is an Android game built end to end:
design system and themes on day 1, game logic, backend, frontend, a real build
and a real emulator smoke test every day, with the repo's own issues, PRs, README
and docs kept current as it goes.

**Why the shape matters.** Most agents are built for one sitting. A *project* has
an arc, dependencies and a timeline longer than your attention span. The bet here
is not a parallel swarm — it's one disciplined contractor, one day at a time,
that reports in every evening. Slower, but a shape you can trust unattended.

**Scope discipline.** This is a side project with a small, fixed time budget, so
every milestone below ends at something demonstrable rather than at a layer. A
half-built orchestrator is worth nothing; one day executed end to end is worth a
great deal.

---

## Decisions locked

| Decision | Choice |
|---|---|
| Language | **Python 3.11+**, stdlib-first — the same shape as the unattended pipelines this design is drawn from |
| Agent driver | **Drive the user's own `claude` CLI** as a subprocess. Longhaul never implements login |
| v0.1 scope | **Narrow build, wide schema** — ship Planner → Coder → DevOps → GitOps; specify every other role in the schema and role registry so nothing gets rewritten later |
| First real run | **An Android game**, 14 days, Flutter + Flame — it exercises every role and produces something installable to screenshot each day |
| License | MIT, `Copyright (c) 2026 Cybiqon AI Solutions` |
| Deps | `pyyaml` only. Telegram and GitHub over stdlib `urllib` — nothing to install, nothing to break on a machine-level pip change |

**Why the CLI driver, not the Agent SDK.** `claude -p --output-format json`
returns `session_id`, `total_cost_usd` and a per-model cost breakdown — the cost
ledger and cross-day session resume come free. `--json-schema` makes the
Planner's output a validated contract instead of parsed prose. And it runs on the
user's own subscription at no marginal token cost, which is what makes a 14-day
unattended run affordable at all. Keep a `AgentDriver` seam so an SDK driver can
land later without touching the orchestrator.

---

## Build status — 30 Aug 2026

Marked against this plan as it is built. `✅` runs and is tested; `🔨` partially
built; `—` not started. **Nothing has yet executed a full day end to end** — the
Coder writes code and DevOps verifies it, but nothing is committed or pushed.

| Piece | Status |
|---|---|
| `doctor` · `gate` · `plan` · `simulate` · `run` · `status` | ✅ |
| `init` · `report` · `ui` · `rollback` · `kill` | — |
| **Planner** | ✅ real 14-day plan, $0.72, committed as `examples/android-game/plan.yaml` |
| **Orchestrator** | ✅ selects, isolates, runs, gates, builds, commits, pushes, opens a PR |
| **Coder** | ✅ implements one task in a worktree, retries with the real error |
| **DevOps/QA** | ✅ **deterministic, not an agent** — see the note under §DevOps below |
| **Git Ops** | ✅ conventional commit, push, PR, **and verifies a CI run actually started** |
| **Notifier** | — next slice |
| **Supervisor** | 🔨 retry budget and attempt counting only; no ceilings, no loop detection |
| Designer · Assets · Reviewer · Scribe · Issues | — |
| `plan.yaml` + `state.json` contracts | ✅ validated hard, 87 tests |
| Cheat gate | ✅ runs before the build, blocks the task |
| secrets gate | ✅ blocks before push; `# longhaul: allow-secret` pragma warns on every use |
| deps · coverage ratchet gates | — |
| Proof gate | — |

**Changed from this plan while building it:**

1. **DevOps is deterministic, not an agent.** Running `flutter test` needs no
   judgement, and asking a model whether the tests passed reintroduces exactly
   the self-report this project exists to remove. Interpreting a failure *does*
   need judgement, and that happens where it belongs — the raw output is fed
   back to the Coder on retry. `core/devops.py`.
2. **The cheat gate runs before the build, not after.** No point spending a
   build on a diff that is already disqualified, and a test asserts the ordering.
3. **`report` moved into v0.1** (from v0.5) — a static timeline is the debugging
   surface for the orchestrator, and reading `state.json` by hand stops working
   around day three.
4. **Every diff is taken against a pinned base commit, never `HEAD`.** The first
   live run's Coder committed its own work, which made a HEAD-relative diff empty
   and the gates blind to 761 insertions. The base is now recorded when the
   worktree is created and persisted in `state.json`.
5. **Creating a CI workflow is allowed; modifying one is not.** The blanket
   protected-path rule blocked a task whose acceptance criteria required writing
   CI. Adding a check is building the gate; changing one is lowering it.
6. **Git Ops is deterministic too.** A conventional commit message is derivable
   from the task and its acceptance criteria; a model would spend money to
   produce something less consistent. Same reasoning as DevOps.
7. **Deleted tests are counted net, not gross.** Blocking a rewrite that adds
   more tests than it removes teaches an agent never to touch tests at all,
   which is the opposite of the intent.

---

## Registry facts (checked, 30 Aug 2026)

| Name | Status |
|---|---|
| `github.com/cybiqon-ai/longhaul` | **free** |
| PyPI `longhaul` | **TAKEN** — an unrelated single-release MLX fine-tuning CLI (0.1.0, May 2026) that also installs a `longhaul` command |
| PyPI `longhaul-ai`, `longhaul-cli` | free |
| npm `longhaul` | free (irrelevant now) |
| `longhaul.dev`, `longhaul.sh` | **REGISTERED** — both on Cloudflare. The spec's claim that `.dev` is clean is wrong |
| `longhaul.build`, `longhaul.run` | free |
| GitHub org `Longhaul` | taken (dormant, 2013-era) |
| `longhaul-bench` ×2 | small agent-benchmark repos; adjacent but not competing |

**Take:** distribution name `longhaul-ai`, import package `longhaul`, console
script `longhaul`. Install reads `uv tool install longhaul-ai`, then `longhaul init`.
Register `longhaul.build` if a domain is wanted.

---

## Corrections the spec/README require

1. **Delete "sign in with your existing Claude Code session."** Anthropic's Agent
   SDK terms: *"Anthropic does not allow third party developers to offer claude.ai
   login or rate limits for their products."* The legitimate path is that the
   **user** runs `claude setup-token` themselves and exports
   `CLAUDE_CODE_OAUTH_TOKEN`, or sets `ANTHROPIC_API_KEY`. Longhaul reads env, never
   authenticates.
2. **Branding.** Longhaul may not be branded "Claude Code" or mimic its visuals.
   "Powered by Claude" is permitted.
3. **`npx longhaul init` → `uv tool install longhaul-ai`.**
4. **`longhaul.dev` is not available.** Fix the README before it ships.
5. **Auto-merge stays off by default** — the spec is right, and this is the single
   biggest trust decision. Keep it prominent.

---

## Architecture

### Agent roles

`v0.1` = implemented now. `spec` = defined in the role registry and plan schema,
implemented later. Each role is a markdown prompt in `src/longhaul/roles/`,
written as a numbered protocol ("▶ STEP N", "run autonomously, there is nobody
to answer").

| Role | Responsibility | When |
|---|---|---|
| **Planner** ✅ | target.md → dependency-ordered day-sized task graph with acceptance criteria and risk flags | Once at init; re-invoked on re-plan |
| **Orchestrator** ✅ | Loads state + plan, picks today's task, dispatches, decides retry vs escalate | Daily |
| **Coder** ✅ | Implements today's task in an isolated worktree; writes code *and* tests | Per task |
| **DevOps/QA** ✅ | Build, lint, typecheck, test — reports structured pass/fail with real errors. **Implemented deterministically rather than as an agent**: running the suite needs no judgement, and a model reporting on its own tests is the self-report this project removes | Per task |
| **Git Ops** ✅ | Worktree, conventional commit, push, open PR, and verify a CI run actually started. Deterministic, not an agent | Per task |
| **Notifier** — | Telegram digest, failure alerts, decision requests | Every interesting transition |
| **Supervisor** 🔨 | Wraps every agent call: retry budget, loop detection, cost/time ceilings, hard halt | Continuous |
| **Designer** `v0.3` | Day-1 design system (palette, type scale, spacing, motion, tone) + per-screen specs. Later UI tasks are checked against it | Once, then per UI task |
| **Assets** `v0.3` | Sprites, icons, audio; writes `assets/CREDITS.md` with license provenance | Per asset task |
| **Reviewer** `v0.4` | Diffs the change against the task's acceptance criteria; flags scope creep, security, breaking changes; writes ADRs | Per task, pre-merge |
| **Scribe** `v0.4` | README, CHANGELOG, `docs/devlog/day-NN.md`, and the repo's `.okf/` knowledge bundle | Per task |
| **Issues** `v0.4` | Opens a GitHub issue per planned task, closes on merge, files bugs on failure, maintains labels/milestones | Per task |

### The daily loop

```
trigger (cron / systemd / GitHub Actions schedule)
  → flock + timeout          ← house rule: no overlap, no infinite hang
  → preflight (doctor --quick)  ← is `claude` still logged in?
  → Orchestrator: load .longhaul/{plan.yaml,state.json}, pick next eligible task
  → Designer  (if the task is UI and no design system exists yet)
  → Coder     in a git worktree, never on main
  → DevOps    build + lint + typecheck + test
  → Gates     deterministic, non-agent: cheat / secrets / deps / coverage ratchet
  → Proof     does it actually RUN? build artifact + screenshot + vision check
  → Reviewer  diff vs acceptance_criteria
       ├ fail → structured feedback → Coder (--resume that session), bounded retries
       └ pass ↓
  → Git Ops   commit, push, open PR, link issue
  → CI        the source of truth — verify a run actually STARTED, then wait
  → Scribe    PROGRESS.md, devlog, CHANGELOG, .okf/
  → state.json + ledger.jsonl written atomically
  → Notifier  "Day 4/14 done: auth ✅ · next: rate limiting · $2.14 · 3 slipped"
```

Everything after task selection is idempotent and resumable. Kill it mid-run;
tomorrow resumes from state, not from scratch.

### Contracts

**`.longhaul/plan.yaml`** — the contract between Planner and everything
downstream. Extends the spec's schema with the fields the wider roles need, so it
never has to break:

```yaml
project: "Neon Drift — one-thumb arcade game"
target_days: 14
profile: flutter-android
milestones:
  - id: m1
    title: "Playable core loop"
    days: [1, 2, 3, 4]
    tasks:
      - id: t2
        day: 2
        kind: feature            # feature | design | asset | docs | infra | fix
        title: "Tap-to-reverse core loop"
        acceptance_criteria:
          - "Tapping reverses direction within one frame"
          - "engine/ imports neither Flutter nor Flame"
          - "Headless bot completes level 1"
        depends_on: [t1]
        surfaces: [game]         # game | backend | frontend | docs
        estimate_minutes: 90
        risk: low
        needs_human: false       # true ⇒ park, don't halt
        proof:                   # what "it works" means for this task
          kind: emulator_screenshot
          expect: "a moving dot on a loop, dark theme, no debug banner"
risk_flags:
  - "Day 9–10 (IAP) needs a human decision on product IDs"
```

**`.longhaul/state.json`** — per-task status, attempt counts, session ids,
timestamps, worktree paths, PR/issue numbers, gate results. Human-readable,
committed, atomically written.

**`.longhaul/config.yml`** — profile, gate toggles, cost/time ceilings, notifier
config, `auto_merge: false`, protected paths.

### On-disk layout in the target repo

```
.longhaul/
├── config.yml
├── plan.yaml
├── state.json
├── ledger.jsonl          one line per agent call: role, session_id, cost, tokens, duration, outcome
├── velocity.json         estimate vs actual, per task
├── runs/day-07/*.jsonl   raw stream-json — the audit trail
├── proof/day-07/         screenshot.png, app.apk, build.log, junit.xml
└── worktrees/            gitignored
PROGRESS.md               appended daily
docs/devlog/day-07.md     public-facing daily writeup
docs/adr/0003-*.md        architecture decisions, written by Reviewer
.okf/                     the project's own knowledge bundle
```

No external database. Kill it, restart tomorrow, it picks up exactly where it
left off — and every decision it made is readable in git.

---

## Features to add beyond the spec

The spec covers roles, retries and Telegram. These are the gaps that decide
whether a 14-day unattended run produces a working Android game or fourteen days
of plausible-looking commits.

### 1. Memory — a knowledge bundle, not just a state file `— not started`
`state.json` tracks *progress*; nothing tracks *knowledge*. On day 20 the Coder
has no idea why day 4 chose Flame over raw Canvas, so it re-litigates or
contradicts it. Longhaul should build and maintain an **OKF knowledge bundle** in
the target repo as a first-class artifact: every agent reads it before acting,
Scribe updates it after every task, and `okf_validate.py --strict` gates it.
OKF is an existing open specification with an existing validator, so this costs
almost nothing to adopt. No competing project has a durable project memory — it
is the strongest thing Longhaul can ship.

### 2. The cheat detector — deterministic anti-slop gates `✅ BUILT`
The dominant long-horizon failure is not bad code, it's the agent making the
*gate* pass instead of the *code* work. Enforce mechanically, from the diff, with
no model in the loop:
- test count may not decrease (**ratchet**), coverage may not decrease
- no new `skip` / `xfail` / `@Ignore` / `it.only` / commented-out assertions
- lint, typecheck and `analysis_options.yaml` may only get **stricter** — diff the config
- `.github/workflows/**` is a protected path: changes always escalate
- no new empty `catch`/`except: pass`, no assertion-free tests, no `return true` stubs
This is *report a count, not a status* applied to an agent. A green check that
ran zero tests is the failure this gate exists to prevent.

### 3. The Proof gate — does it actually run? `— not started`
Tests passing ≠ the app works. Every task declares what proof means. For the
Android game: build APK → boot emulator → `adb install` → drive it → screenshot →
a vision check that the screenshot matches the day's acceptance criteria *and*
the design system. For web: Playwright + screenshot. Artifacts land in
`.longhaul/proof/day-NN/`, so "day 7 shipped" is a picture, not a claim. Without
this, "end to end" is not real.

### 4. Designer and a design system on day 1
Day 1 produces `design/design-system.md` — palette, type scale, spacing, motion,
tone of voice — plus per-screen specs. Every later UI task is diffed against it,
which is what stops the app drifting into template mush by day 10. Asset pipeline
generates or sources sprites/icons/audio and writes `assets/CREDITS.md` with
license provenance (boring, and the thing that gets an app pulled).

### 5. Velocity and honest re-planning — not a v1.0 feature
The spec defers plan re-negotiation to v1.0. That's too late: plan drift is what
kills multi-day autonomy. Track estimate vs actual per task from day 1; a weekly
retro run re-plans the remaining days from measured velocity and reports the slip
plainly — *"Day 8/14, 5 done, 3 slipped, forecast Day 17."* A deadline forecast
the tool refuses to flatter is the whole point of tracking one.

### 6. Budget, ceilings and a kill switch `🔨 ledger built; ceilings not`
`total_cost_usd` arrives free in every `--output-format json` response. Enforce
per-task, per-day and per-project ceilings plus wall-clock caps in the
Supervisor — not by asking the agent to police itself. `longhaul kill` stops
everything; `.longhaul/ledger.jsonl` is the receipts.

### 7. Repo citizenship — issues, PRs, README, docs, releases `🔨 PRs built; issues, CHANGELOG, releases not` `🔨 PRs built; issues, CHANGELOG, releases not`
What you asked for, made concrete: an issue per planned task (so the tracker
*is* the visible plan), closed by its PR; failures file bug issues; labels and
milestones mirror plan milestones; CHANGELOG generated from conventional commits;
README kept current; a tagged GitHub Release with the APK attached at every
milestone; and a public `docs/devlog/day-NN.md` — which doubles as marketing for
both Longhaul and whatever it builds.

### 8. `longhaul doctor` — preflight, before day 1 and before every run `✅ BUILT`
Verify `claude` is installed **and still authenticated**, git identity and remote
write access, the profile's toolchain (Flutter/Gradle/Java/emulator), disk space,
CI wired, secrets present. Refuse to start otherwise.
**This encodes a failure that has already been paid for in production:** a
scheduled pipeline whose Claude CLI had logged out reported `OAuth session
expired` in a way that read as success, and ran empty for four consecutive
nights. Longhaul treats that as a hard, loud failure.

### 9. Project profiles `✅ BUILT` (one: flutter-android)
`profiles/flutter-android.yml`, `nextjs-web.yml`, `python-api.yml`, … carrying
build/test/lint/run/smoke commands and gate definitions, so DevOps never guesses
at a stack. Users add their own; this is how Longhaul stays honest across
languages, and it's the natural first contribution for an outsider.

### 10. Worktrees, checkpoints, rollback `🔨 worktrees built; tags and rollback not`
Each task runs in a `git worktree`, not just a branch, so a wedged day can't
break the main checkout. Every completed day is a tag → `longhaul rollback day-7`.
Optional Docker for full isolation.

### 11. Escalate without halting
A single ambiguous decision should not stop a 14-day project. Park the task in a
`needs-human` queue, continue with unblocked tasks, and record the resolution as
an ADR. Telegram commands `/status /pause /resume /approve /skip /logs`, with the
notifier pluggable (Slack, Discord, webhook).

### 12. Security gates `✅ secrets gate built; dependency audit not` `✅ secrets gate built; dependency audit not`
Secret-scan every diff before push; dependency audit; always escalate changes to
auth, payments, CI, infra credentials or anything matching a secret pattern.
Non-negotiable for a tool that pushes unattended. A credential committed by an
agent is not a hypothetical: tokens end up in `.git/config` remotes and in
`.env` files that a well-meaning `git add -A` will happily stage.

### 13. `longhaul simulate` `✅ BUILT`
Run the Planner only and print the 14-day arc with no code written and almost no
spend, so you can read the plan before committing two weeks to it.

### 14. Per-role model and effort selection
Planner and Reviewer benefit from high effort; mechanical tasks don't. Configure
`--model` and effort per role; use `--resume <session_id>` on retries so the Coder
gets the failure in context instead of re-reading the repo. Handle
`system/api_retry` events so a 429 doesn't burn a retry budget.

---

## The dashboard

The README promises a dashboard at `localhost:4321`, and for an OSS project it is
not a nice-to-have: **it is the README screenshot.** A timeline of fourteen green
days with a game screenshot under each is the single most persuasive artifact
this project can produce. It is also how you debug the orchestrator — reading
`state.json` by hand stops working on about day three.

### How it's built — no npm, no build step

Two commands, one renderer, matching `okf_visualize.py`'s pattern exactly
(self-contained HTML, no backend, no data leaves the page):

- **`longhaul report`** → writes a single self-contained `report.html` from
  `.longhaul/`. No server. Committable, attachable to a release, viewable from a
  CI artifact, and readable on a machine that never ran the agent.
- **`longhaul ui`** → stdlib `http.server.ThreadingHTTPServer` on **:4321** serving
  that same page plus a small JSON API over `.longhaul/`, with live updates by
  **SSE** (`text/event-stream`) tailing the active run's JSONL.

One HTML template, one CSS file, one vanilla-JS file, shipped as package data.
Charts are inline SVG. Zero runtime dependencies, zero build toolchain, and the
Python package stays `pyyaml`-only.

### Views

| View | What it shows |
|---|---|
| **Today** *(default)* | The running task, which role is active, live streamed output, elapsed time, spend against today's ceiling, gate results as they land |
| **Timeline** | The day strip — done / failed / in-progress / parked / skipped, with cost, duration and retry count per day. Click through to a day |
| **Day detail** | The task, **each acceptance criterion with its own pass/fail**, the diff, test results, every gate with its reason, the proof artifact inline, PR and issue links, and the raw run JSONL |
| **Proof gallery** | Every day's screenshot in one strip — a game visibly appearing over fourteen days. This is the marketing asset |
| **Plan** | The remaining dependency graph with the velocity forecast and honest slip. **Editable** — the README's "editable if reality diverges" promise |
| **Spend** | Cost per day, per role, cumulative against ceiling, forecast to completion, from `ledger.jsonl` |
| **Needs you** | The parked queue: decisions, tasks past their retry budget, security escalations — each with Approve / Skip / Retry / Edit |

### Design rules

- **One command layer.** `/approve` from Telegram and the Approve button call the
  same `core/commands.py` function. Two front-ends, never two implementations.
- **Read-only by default; every write is a git diff.** Approving, skipping or
  editing the plan writes to `.longhaul/` — which is committed. No hidden state
  mutation, and the history of your interventions is in the repo.
- **Binds `127.0.0.1` only.** The page shows source, diffs and agent output.
  Exposing it needs an explicit `--host` flag and prints a warning.
- **Secrets redacted server-side**, before streamed output reaches the browser.
- **Works with the agent stopped.** It renders from disk, so it is equally a live
  monitor and a post-mortem.
- **`longhaul report --static docs/dashboard/`** — publishable to GitHub Pages, so
  the demo game's dashboard is a public, linkable proof artifact.
- Dark/light, keyboard-navigable, no framework.

### Staging

`report` lands in **v0.1** because it is the debugging surface — a static
timeline is worth more early than late. `ui` with SSE lands in **v0.2**.
Interactive actions land in **v0.4**, alongside the Telegram commands they share
a command layer with. Plan editing lands in **v0.5** with velocity.

---

## Repo layout — `oss/longhaul/`

```
longhaul/
├── pyproject.toml           name = "longhaul-ai"; [project.scripts] longhaul = "longhaul.cli:main"
├── src/longhaul/
│   ├── cli.py               argparse subcommands: init doctor plan simulate run status report rollback kill ui
│   ├── core/
│   │   ├── orchestrator.py  the state machine
│   │   ├── state.py         atomic load/save
│   │   ├── supervisor.py    retry budget, loop detection, ceilings
│   │   ├── commands.py      approve/skip/retry/pause — shared by UI and Telegram
│   │   └── velocity.py
│   ├── ui/
│   │   ├── render.py        .longhaul/ → self-contained report.html
│   │   ├── server.py        stdlib http.server on :4321 + SSE
│   │   └── assets/          index.html, app.css, app.js  (package data, no build)
│   ├── driver/
│   │   ├── base.py          AgentDriver interface
│   │   └── cli_driver.py    `claude -p --output-format json --json-schema ...`
│   ├── roles/*.md           agent prompts, shipped as package data
│   ├── gates/               cheat.py secrets.py deps.py coverage.py proof.py
│   ├── profiles/*.yml       flutter-android, nextjs-web, python-api
│   ├── integrations/        github.py telegram.py   (stdlib urllib)
│   └── schema/              plan.py state.py + generated JSON Schema for --json-schema
├── templates/               target.md, .github/workflows/longhaul.yml, cron snippet
├── examples/android-game/   target.md + the generated plan.yaml
├── tests/                   pytest
├── docs/                    architecture.md safety-and-guardrails.md writing-a-target-file.md profiles.md adr/
├── .okf/                    knowledge bundle — ground rule 2, same day
├── .github/workflows/ci.yml
├── CLAUDE.md README.md ROADMAP.md CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md LICENSE
```

**The scheduled-entrypoint pattern.** A working shape for the daily trigger:
`flock` and `timeout` around `claude -p`, then a verification step that reads a
ledger to confirm the run actually produced output rather than trusting exit 0.
Generalise that rather than re-deriving it.

**The notifier contract.** `send()` returns `{"ok", "message_id"}` and never
raises — alerting must not be able to crash the thing it is reporting on. A
confirmed `message_id` is also the only honest evidence a notification landed.

---

## Milestones

Sized for 1–2 h/day. Each ends at something demonstrable.

- **v0.1 — it does one day** 🔨 `doctor` ✅ · `gate` ✅ · `plan` ✅ · `simulate` ✅ ·
  `run` ✅ · `status` ✅ · `init` — · `report` —.
  Planner ✅ → Coder ✅ → DevOps ✅ → GitOps —. State ✅, cost ledger ✅,
  worktrees ✅; PR-only, no auto-merge, Telegram notify-only and the manual
  trigger still to come. Full plan schema and role registry ship complete even
  though half the roles are unimplemented ✅.
- **v0.2 — it does many days unattended** Supervisor (retry with real error
  feedback, loop detection, ceilings), the cheat-detector gates, scheduling (cron
  + systemd + GitHub Actions template), resume-after-crash, **`ui` live on :4321**.
- **v0.3 — it makes something you can look at** Designer, design system, asset
  pipeline, the Proof gate (emulator + screenshot + vision check), profiles,
  **the proof gallery**.
- **v0.4 — it runs the repo** Reviewer + ADRs, Scribe (README/CHANGELOG/devlog/
  `.okf/`), Issues agent, Telegram commands and **the dashboard's Needs-you
  actions over one shared command layer**, releases with artifacts.
- **v0.5 — it tells the truth about the deadline** Velocity, re-planning, retro
  run, **editable plan view**, `report --static` for GitHub Pages.
- **v1.0** Multi-repo workspaces (frontend + backend), pluggable notifiers, a
  plugin API for third-party roles and gates.

**First real run:** a 14-day Flutter + Flame Android game, `examples/android-game/target.md`.
It exercises every role — design, assets, game logic, build, emulator proof,
release — and produces something installable to screenshot each day.

---

## Risks and known traps

| Risk | Handling |
|---|---|
| **CI silently never runs.** GitHub does not trigger workflows on commits pushed with the default `GITHUB_TOKEN`. "CI is the source of truth" then quietly means nothing checked it | Push as a GitHub App or PAT, and **verify a CI run actually started** before waiting on it. Exactly the ground-rule-3 failure shape |
| **The `claude` CLI logs out mid-project** — `OAuth session expired` swallowed as success, 4 nights lost here already | `doctor --quick` before every run; treat auth failure as a loud halt with a Telegram alert, never a skip |
| Scheduled workflows on public repos disable after 60 days idle | Longhaul commits daily, so activity is continuous — but document it |
| `claude-code-action` rejects bot actors on scheduled runs | List the actor in `allowed_bots` |
| Agent deletes tests to go green | Cheat-detector ratchets (feature 2) |
| Runaway spend | Supervisor ceilings + ledger + `longhaul kill` |
| Secrets pushed to a public repo | Secret-scan gate before every push |
| `~/.claude.json` registers MCP servers **per project directory** | Moving the repo strips them — documented trap in `.okf/infra/cron.md` |

---

## Verification

**v0.1 is done when this sequence works, unaided:**

```bash
uv tool install longhaul-ai
cd /tmp/neon-drift && git init
longhaul doctor                    # must FAIL loudly if `claude` is logged out
longhaul init --target target.md --days 14 --profile flutter-android
longhaul simulate                  # prints the 14-day arc, near-zero spend
longhaul run                       # one full day
longhaul status
longhaul report                    # self-contained report.html, opens in a browser
```

Then check, on disk and on GitHub:

- `.longhaul/plan.yaml` validates against the schema; every task has
  `acceptance_criteria` and `depends_on`; the graph is acyclic and day-ordered
- `.longhaul/state.json` and `ledger.jsonl` exist, with a real `session_id` and a
  non-zero `total_cost_usd`
- work happened in `.longhaul/worktrees/`, **never** on `main`
- a branch was pushed and a PR opened; **a CI run actually started on it**
- `PROGRESS.md` appended; a Telegram message arrived with a **count**, not a status
- `longhaul run` a second time on the same day is a no-op (idempotent)
- `kill -TERM` mid-run, then `longhaul run` again → resumes, no duplicate commit
- `report.html` opens with no network access, renders the day, and contains no
  secrets — grep the output for token patterns before it is ever committed
- `longhaul ui` binds `127.0.0.1` only; confirm with `ss -ltnp | grep 4321`

**Gate tests (pytest, no model in the loop)** — feed the cheat detector crafted
diffs and assert it blocks: a deleted test, an added `@pytest.mark.skip`, a
loosened `analysis_options.yaml`, an edited workflow file, an `except: pass`.

**Repo hygiene:**

```bash
python3 tools/okf_validate.py .okf --strict
ruff check . && pytest
```

**The real acceptance test** is the 14-day game run: fourteen daily commits,
fourteen devlog entries, an installable APK at the end, and a screenshot from
each day's Proof gate. If it slips, the retro should say so in plain numbers.
