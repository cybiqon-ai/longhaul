# Update Log

## 2026-08-30

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
