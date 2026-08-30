# Longhaul

**Give it a target and a deadline. It ships a day's worth of work every day, and only wakes you when something needs a human.**

Every other coding agent is built for one sitting: you open a terminal, you drive,
it does a task, you review. That is the wrong shape for a *project* — something
with an arc, dependencies between pieces, and a timeline longer than your
attention span.

Longhaul is not a swarm that fires off twenty workers in parallel and hopes they
don't collide. It is the opposite bet: **one disciplined contractor, one day at a
time, who reports in every evening.** Slower, and a shape you can trust to run
while you are not watching.

```console
$ longhaul init --target target.md --days 14 --profile flutter-android
  planned 14 days · 6 milestones · 31 tasks · 4 risk flags

$ longhaul run
  day 3/14  neon-drift
  ├─ coder      tap-to-reverse core loop            2m 41s   $0.38
  ├─ devops     flutter analyze · 214 tests         1m 03s   ✓ 214 passed
  ├─ gates      cheat ✓  secrets ✓  coverage 71%→73% ✓
  ├─ proof      emulator screenshot                 0m 52s   ✓ matches criteria
  └─ gitops     PR #12 opened · CI run 4471 started
  day 3 done · $0.51 · 3/14 · next: level generator
```

---

## Why you would use it

- **A real plan, not a to-do list.** The Planner produces a dependency-ordered
  task graph with explicit acceptance criteria per day. Every downstream agent
  checks its work against *that*, not against vibes.
- **It can't cheat the gate.** The dominant failure of long-running agents is not
  bad code — it is the agent making the *test* pass instead of making the *code*
  work. Longhaul enforces a ratchet from the diff, with no model in the loop:
  test count can't drop, coverage can't drop, no new `skip`/`xfail`, lint and
  typecheck config can only get stricter, CI files are protected.
- **Proof, not self-report.** A task isn't done because the agent said tests
  passed. It builds, installs on an emulator, screenshots, and checks the
  screenshot against the day's acceptance criteria. Every day leaves an artifact
  on disk.
- **It remembers.** Longhaul maintains a knowledge bundle in your repo, so the
  agent on day 20 knows what day 4 decided and why, instead of quietly
  contradicting it.
- **An honest deadline.** It tracks estimate against actual and tells you
  *"day 8 of 14, five done, three slipped, forecast day 17."* It will not flatter
  the plan.
- **Guardrails by default.** Bounded retries with the real error fed back, a
  watchdog that halts on loops instead of burning tokens for six hours, cost
  ceilings enforced by the orchestrator, and **no auto-merge to `main` unless you
  turn it on yourself, per repo.**

---

## Status

**Pre-alpha.** It plans a project and it runs a day's work — in an isolated
worktree, gated, built and tested, with state written atomically so a killed run
resumes rather than restarts.

```bash
longhaul init --profile flutter-android   # config, target skeleton, doctor
longhaul plan --days 14                   # a real dependency-ordered plan
longhaul run                              # one day's work, gated and tested
longhaul ui                               # watch it on localhost:4321
```

It does **not** yet commit, push, or open a PR — Git Ops, the Notifier, and the
Supervisor's cost and wall-clock ceilings are the next slice. See
[`plan.md`](plan.md) for the design, with live build-status markers, and
[`ROADMAP.md`](ROADMAP.md) for what lands when.

Watch it, don't depend on it.

---

## How it will work

```
target.md ──▶ Planner ──▶ .longhaul/plan.yaml   (day-by-day task graph)
                                │
                      ┌─────────▼─────────┐
                      │   Orchestrator    │  ← once per day (cron / systemd / Actions)
                      └─────────┬─────────┘
                                │  picks today's task, dispatches
        ┌───────────┬───────────┼───────────┬───────────┐
        ▼           ▼           ▼           ▼           ▼
     Designer     Coder      DevOps       Gates       Proof
   design system  in a       build,     cheat,      does it
   + screen specs worktree   lint,      secrets,    actually
                             test       coverage    RUN?
        └───────────┴───────────┼───────────┴───────────┘
                                │
                           Reviewer — diff vs acceptance criteria
                    ┌───────────┴───────────┐
                   pass                    fail
                    │                       │
          commit, push, PR,        retry with the real error
          CI is the source          (bounded) → still failing
          of truth                  → halt + alert you
                    │
       state, devlog, docs, Telegram digest
```

Everything lives in a human-readable `.longhaul/` folder committed to your repo —
no external database, no hidden state. Kill it mid-run and tomorrow's run picks
up exactly where it left off.

---

## Safety notes — read before pointing it at anything real

Longhaul pushes code, unattended, for days at a time. Some defaults exist
specifically to keep that from going sideways:

- Every task runs in an isolated **git worktree**, never on `main`.
- **Auto-merge is off by default.** Longhaul opens PRs and waits for you.
- **CI is the source of truth**, not the agent's self-report — and Longhaul
  verifies a CI run actually *started*, because a push that silently triggers
  nothing is the same as no CI at all.
- Retry budgets and cost/time ceilings are enforced by the orchestrator, not by
  the agent policing itself.
- Every diff is secret-scanned before it is pushed.
- Security-sensitive changes — auth, payments, CI workflows, infra credentials —
  are escalated to you by design, not left to agent judgement.

See [`docs/safety-and-guardrails.md`](docs/safety-and-guardrails.md).

---

## Requirements

Longhaul drives [Claude Code](https://claude.com/claude-code), which you install
and authenticate yourself. **Longhaul never handles your login.** Set one of:

```bash
export ANTHROPIC_API_KEY=...          # a key from the Claude Console
# or, on a Pro/Max/Team/Enterprise plan:
claude setup-token                    # then export CLAUDE_CODE_OAUTH_TOKEN=...
```

Then `longhaul doctor` will tell you what else your project profile needs.

---

## What it is not

- **Not a swarm.** It runs one task at a time, on purpose. Parallel agents on a
  shared repo is a merge-conflict generator, not a productivity multiplier.
- **Not a replacement for reading the diff.** It opens PRs so that you review
  them. Auto-merge exists, is off, and should stay off until you trust a repo.
- **Not autonomous in the interesting sense.** It follows a plan a model wrote
  and you approved. When reality diverges it stops and says so rather than
  improvising.
- **Not a Claude Code product.** Longhaul is an independent open-source tool that
  runs on Claude. It is not affiliated with or endorsed by Anthropic.
- **Not an SEO play.** GitHub README links are `nofollow`; this repository cannot
  pass PageRank and was not built to. It is a credibility artifact.

---

## Contributing

MIT licensed and built in the open. [`CONTRIBUTING.md`](CONTRIBUTING.md) has the
setup steps. The most useful contribution right now is a **project profile** — the
build/test/lint/run commands for a stack Longhaul doesn't cover yet. See
[`docs/profiles.md`](docs/profiles.md).

"Here is where it got stuck" reports are the most valuable bug reports this
project can receive. Please open them.

## License

MIT — see [`LICENSE`](LICENSE). Copyright © 2026 Cybiqon AI Solutions.
