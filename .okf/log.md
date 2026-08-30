# Update Log

## 2026-08-30

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
