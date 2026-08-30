# Update Log

## 2026-08-30

* **Update**: The first live `longhaul run` found a **gate bypass**, and it was
  only found by running it — no unit test would have.

  The Coder did the work correctly: 28 files, 761 insertions, a real Flutter
  scaffold with CI, in 592s for $1.99. Then it **committed its own work**.
  `worktree.diff()` compared against `HEAD`, which was now the Coder's commit,
  so the diff was empty, the cheat gate examined nothing, and the run reported
  "the coder changed nothing" while a complete day's work sat on disk.

  It failed safe by accident. The real flaw is that **an agent that commits
  makes the gates blind** — a cheat committed rather than left in the working
  tree would have been waved through. Fixed by pinning the base commit when the
  worktree is created (`Worktree.base_sha`, persisted in `state.json`) and
  taking every diff against that, never `HEAD`. Three regression tests, one of
  which asserts the HEAD-relative diff is empty — the bug, pinned in place. The
  Coder prompt now also says committing is Git Ops' job.

* **Update**: The protected-path rule blocked a **new** `.github/workflows/ci.yml`
  written by the Coder — but task t1's acceptance criteria explicitly require CI
  that ships a debug APK, so the gate was stopping legitimate work. The rule now
  distinguishes **creating** a workflow (allowed — adding a check is building the
  gate) from **modifying** one (blocked — that is lowering it). Weakening a new
  workflow is still caught, because `continue-on-error: true` is matched on any
  added line wherever it appears.

  With both fixed, the real day-1 artifacts pass the whole pipeline: 23 files
  checked, 0 blocking, and `install ok · lint ok · test ok · build ok · tests 3`
  from a genuine `flutter analyze`, `flutter test` and `flutter build apk`.

* **Creation**: [The day loop](/architecture/the-day-loop.md), and with it the
  Coder and DevOps roles — `core/orchestrator.py`, `core/state.py`,
  `core/worktree.py`, `core/devops.py`, `schema/state.py`, `roles/coder.md`, and
  the `run` and `status` commands. Three of twelve roles now exist as code.

  Two properties are tested rather than assumed, because without both the tool
  is not safe to schedule: **idempotent** (running twice in a day does not do
  the work twice) and **resumable** (killed at any point, the next invocation
  continues from `state.json`). State is written with a temp file and an atomic
  rename, and the ledger reader tolerates a torn final line — a run killed
  mid-write must lose one step, never the project's whole memory.

* **Update**: **DevOps is implemented deterministically, not as an agent** — a
  departure from `plan.md`, recorded there too. Running the test suite requires
  no judgement, and asking a model whether its own tests passed reintroduces
  exactly the self-report this project exists to remove. Interpreting a failure
  does need judgement, and that happens where it belongs: the raw build output
  is fed back to the Coder on retry, with an explicit instruction not to weaken
  the check that caught it.

* **Update**: The cheat gate now runs **before** the build rather than after,
  with a test asserting the ordering. There is no point spending a build on a
  diff that is already disqualified, and without the test the ordering would
  drift silently and cost a build per rejected attempt.

* **Update**: `longhaul status` reported `pending: 0` while seventeen tasks were
  undone, because the count only saw tasks `state.json` had already created. A
  count that silently omits everything not yet started is the failure this
  project is named for; fixed, with a test.

* **Update**: `plan.md` now carries live build-status markers — a status table
  near the top and ✅/🔨/— against every role, feature and milestone — so the
  design document and the state of the code cannot drift apart unnoticed. It
  also records the three decisions changed while building: deterministic DevOps,
  gate-before-build, and `report` moved into v0.1.

* **Creation**: [The plan contract](/architecture/plan-contract.md) and the
  Planner — the first of the twelve roles to exist as code rather than as a
  specification. `schema/plan.py`, `core/planner.py`, `roles/planner.md`, a
  profile loader, and `longhaul plan` / `longhaul simulate`.

  The Planner is given **read-only tools** (`Read`, `Glob`, `Grep`) and a test
  asserts `Edit`, `Write` and `Bash` are absent: a planning step that can edit
  the repository is one that cannot be safely re-run.

* **Update**: [Longhaul](/product/overview.md) and
  [agent roles](/architecture/agent-roles.md) revised — one role built, eleven
  still specifications, and still no orchestrator. The Planner produces a plan;
  nothing yet consumes one.

* **Update**: Two bugs in `doctor`, both found by running it against a real
  machine rather than against the test suite, and both the same shape — a check
  that reported confidently about something it had not actually tested.

  First, it required `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` in the
  environment and failed without one. But the primary path this tool is built
  for is the CLI's own stored subscription login, where neither variable exists.
  It failed on a perfectly working machine.

  Second, and worse: the round-trip used `claude --bare`, and **bare mode never
  reads OAuth credentials or the system keychain**. So the preflight check was
  exercising a different credential path from the one the driver actually uses —
  a check that can fail while the real work would succeed, and, more dangerously,
  could have passed while the real work failed. Both are fixed, with regression
  tests, including one asserting `--bare` is absent from the argv.


* **Creation**: Bundle created alongside the repository itself, on the same day as the
  code. Five concepts:
  [Longhaul](/product/overview.md), [agent roles](/architecture/agent-roles.md),
  [gates](/architecture/gates.md), [the Claude driver](/architecture/driver.md)
  and [the dashboard](/architecture/dashboard.md).

  The bundle deliberately separates **what is built** from **what is designed**,
  because on creation day those are very far apart: a driver, one gate, a doctor
  and a CLI surface exist; no orchestrator, no Planner and no executed day do.
  `plan.md` at the repository root is the design document and is much larger than
  this bundle; treating it as a description of working software would be wrong.

* **Creation**: A kill criterion of **30 Sep 2026** for a working v0.1 is written
  into [Longhaul](/product/overview.md), so a project built on evenings cannot
  quietly become an unfinished codebase carried indefinitely.

* **Update**: Two claims in the original `spec.md` were checked and found false,
  and are recorded in [Longhaul](/product/overview.md) so they are not repeated.
  `longhaul.dev` and `longhaul.sh` are both registered, on Cloudflare nameservers,
  contradicting the spec's "no collisions found"; and PyPI `longhaul` is taken by
  an unrelated MLX fine-tuning CLI which also installs a `longhaul` console
  script. The distribution is therefore named `longhaul-ai`. The GitHub repo
  `cybiqon-ai/longhaul` and `longhaul.build` were free on this date.

* **Update**: The spec's README promised users could *"sign in with your existing
  Claude Code session"*. Anthropic's Agent SDK terms do not permit a third-party
  product to offer claude.ai login or subscription rate limits, so that promise
  was removed and the design changed to shell out to a binary the user installs
  and authenticates themselves — see [the Claude driver](/architecture/driver.md).

* **Creation**: [Gates](/architecture/gates.md). The cheat detector is the only
  designed component that runs today. Its first implementation matched swallowed
  exceptions with single-line regexes and therefore missed the two-line
  `except Exception:` / `pass` form entirely — caught by the test suite on the
  first run, before the code was ever committed. Recorded because it is precisely
  the failure shape the gate exists to catch: a check reporting success while
  examining nothing useful.
