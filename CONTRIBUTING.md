# Contributing

Longhaul is pre-alpha. The design is settled enough to build against — read
[`plan.md`](plan.md) first, it is the real specification — but the code is not
stable yet.

## Setup

```bash
git clone https://github.com/cybiqon-ai/longhaul
cd longhaul
uv venv && uv pip install -e ".[dev]"
pytest && ruff check .
```

Python 3.11+. One runtime dependency (`pyyaml`); please don't add a second
without saying why in the PR.

## The most useful thing you can contribute

**A project profile.** A profile is the build/test/lint/run/smoke commands for
one stack, so the DevOps role never has to guess. They live in
`src/longhaul/profiles/*.yml` and are ordinary YAML — no Python required. See
[`docs/profiles.md`](docs/profiles.md).

Missing today: Go, Rust, Django, Rails, Unity, React Native, Swift, Kotlin/JVM.

**A "here is where it got stuck" report.** If you point Longhaul at something and
it derails, the transcript in `.longhaul/runs/` is more valuable to this project
than a feature request. Redact your secrets first.

## Ground rules for code

- **Report a count, not a status.** Anything that can fail silently must print
  how many things it actually did. Exit code 0 means nothing.
- **Gates contain no model.** Everything in `src/longhaul/gates/` is
  deterministic and testable from a diff. If a check needs judgement, it belongs
  in the Reviewer role, not in a gate.
- **One command layer.** An action available in the dashboard and over Telegram
  is implemented once, in `core/commands.py`. Two front-ends, never two
  implementations.
- **Nothing writes outside `.longhaul/` and the worktree** without an explicit
  reason. Longhaul runs unattended in other people's repositories.

## Tests

Gate tests take a crafted diff and assert the gate blocks it — a deleted test, an
added `@pytest.mark.skip`, a loosened lint config, an edited CI workflow. Adding
a gate means adding those.

Anything that shells out to `claude` is mocked in tests. The suite must run
offline, with no credentials, in under a few seconds.

## Commits and PRs

Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).

**Add a `CHANGELOG.md` entry in the same commit**, under `## [Unreleased]`, with
the short hash, the subject, and two or three sentences on what it did. If the
change exists because something broke when you ran it, say so — that is the part
a future reader needs most.

Open an issue before a large change. Small fixes can go straight to a PR.
