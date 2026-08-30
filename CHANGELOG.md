# Changelog

Every commit, with what it actually did. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project is
pre-1.0 and does not yet publish releases, so everything sits under Unreleased.

Entries record what was found as well as what was built — several of the fixes
below exist because running the thing for real broke it, and that is the most
useful part of the history to a reader.

## [Unreleased]

### 2026-08-30

- **`dc3a033` feat(gates): scan every diff for credentials before anything is
  pushed.** `gates/secrets.py` blocks GitHub/Anthropic/OpenAI/AWS/Google/Slack/
  Stripe/Telegram tokens, private keys, credentials embedded in URLs, generic
  secret-looking assignments, and any committed `.env`. Placeholders and
  interpolation holes still pass so docs and examples work. Wired into the day
  loop and into `longhaul gate` alongside the cheat gate.
  It lands *before* the push machinery on purpose: push is the point of no
  return, and rewriting history does not un-leak a token.
  *Found while writing it:* the first version of these tests contained realistic
  credential literals and **GitHub push protection rejected the push** — the
  correct call, since a scanner's own fixtures are the likeliest hiding place for
  a real secret. Every fixture is now assembled by concatenation, so no complete
  credential string exists in any source file. A `# longhaul: allow-secret`
  pragma covers fixtures that genuinely need a credential shape, and every use
  emits a warning rather than being honoured silently.
  *Also found, by running `longhaul gate` on this very diff:* the cheat gate
  counted deleted test functions without counting added ones, so a net-positive
  rewrite was blocked. Now measured net per file — blocking a rewrite teaches an
  agent never to touch tests, the opposite of the intent.

- **`ad4db06` feat(orchestrator): run a day's work — and close a gate bypass
  found by doing it.** `longhaul run` and `longhaul status`: pick the next
  eligible task, isolate it in a git worktree, let the Coder implement it, gate
  the diff, build and test deterministically, record state atomically. Idempotent
  and resumable, both tested. DevOps implemented deterministically rather than as
  an agent.
  *Found by the first live run:* the Coder committed its own work, so a
  HEAD-relative diff was empty and **the cheat gate examined nothing** — 761
  insertions invisible. Diffs are now taken against a base commit pinned at
  worktree creation. Also: the protected-path rule blocked a *new* CI workflow on
  a task that required writing one, so creating a workflow is now distinguished
  from modifying one.

- **`c07d4b2` feat(planner): the first role that exists as code rather than a
  spec.** `longhaul plan` and `longhaul simulate`. `schema/plan.py` validates the
  contract hard — no acceptance criteria, a dependency on a later day, cycles,
  unknown deps, duplicate ids — and reports every problem rather than the first.
  The Planner gets read-only tools, asserted by a test.
  *Found by running it:* `doctor` required an API-key env var and so failed on a
  machine whose `claude` was logged in on a subscription; and it round-tripped
  through `--bare`, which never reads OAuth, so it was testing a different
  credential path from the driver.

- **`86e6102` fix(ci): the workflow YAML never parsed, and nothing noticed.** The
  first push produced a red run with **zero jobs and no logs** — a `: ` inside a
  plain YAML scalar made the file invalid, in the Lint step that prints how many
  findings ruff produced. `tests/test_workflows.py` now parses every workflow and
  asserts it defines jobs and a trigger.

- **`8f24b43` Scaffold Longhaul: the plan, and the parts of it that already
  run.** The design in `plan.md`, plus a CLI surface, `doctor`, a subprocess
  driver for `claude -p`, and the cheat detector. Corrections to the original
  notes: no claude.ai login (SDK terms), `longhaul.dev`/`.sh` are taken, and PyPI
  `longhaul` is taken so the distribution is `longhaul-ai`.
