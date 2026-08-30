---
type: Concept
title: Gates
description: Deterministic diff checks that run before any push, with no model in the loop — the cheat detector is the only part of Longhaul's design that currently works.
resource: https://github.com/cybiqon-ai/longhaul/tree/main/src/longhaul/gates
tags: [architecture, gates, testing, safety, implemented]
timestamp: 2026-08-30T00:00:00Z
---

# Overview

A gate takes a diff and returns findings. It is deterministic and testable by
handing it crafted input. **No model runs inside a gate.** A check that needs
judgement belongs to the Reviewer role, where its opinion is advisory and logged
rather than load-bearing — a gate that can be argued with is not a gate.

`gates/base.py` defines `Finding`, `GateResult` and the `Gate` protocol.
`GateResult.checked` carries how many files were actually examined, because an
empty diff must not read as a pass.

# The cheat detector

`gates/cheat.py` is **built and tested** — the only component of the design that
runs today. It exists because the dominant failure of a long-running coding agent
is not writing bad code; it is making the *gate* pass rather than making the
*code* work. It blocks, from the diff:

- an added skip or ignore marker (`@pytest.mark.skip`, `it.only`, `@Ignore`,
  `t.Skip`, `#[ignore]`, `xit`)
- a removed test function in a test path
- a change to a protected path — `.github/workflows/`, `.longhaul/config.yml`,
  `.pre-commit-config.yaml`
- an error swallowed silently, including the two-line `except Exception:` /
  `pass` form and `continue-on-error: true`

and warns on a change to a lint or typecheck config file, which must be confirmed
to have got stricter rather than looser.

# The two-line bug

The first implementation matched swallowed errors with single-line regexes, so
`except Exception:` followed by `pass` — the form people actually write — passed
straight through. It was caught by the test suite on the first run. The fix pairs
each added line with the next added line, and requires **both** to be additions,
so a pre-existing handler is never flagged.

Worth recording because it is the exact shape of failure the gate exists to
catch: a check that reports success while examining nothing useful.

# The secrets gate

`gates/secrets.py` is **built** and runs before every push, because push is the
point of no return: rewriting history does not un-leak a token.

Its own tests were the first thing it caught. The first version contained
realistic credential literals and **GitHub push protection rejected the push** —
correct, since a scanner's fixtures are the likeliest hiding place for a real
secret. Every fixture is now assembled by concatenation, so no complete
credential string exists in any source file.

A `# longhaul: allow-secret` pragma exists for fixtures that legitimately need a
credential shape. **Every use emits a warning** rather than being honoured
silently: a suppression an agent can add invisibly is a suppression an agent
will add invisibly.

# Comments are not a swallowed error

The gate first treated any comment after an `except` as the handler's body, so
`except PortInUse as exc:` followed by an explanatory comment and then real
handling was blocked — caught by running `longhaul gate` over the UI commit.
Flagging that teaches an agent to stop writing comments, which is the opposite
of what the gate wants. It now looks past comments to the first line that
actually does something. A handler whose **entire** body is a comment still
blocks: that is an explanation standing in for handling.

# Counted net, not gross

Running `longhaul gate` over its own diff blocked a commit for removing three
tests from a file that had been rewritten with more tests than it started with.
Deletions are now counted against additions per file. Blocking a net-positive
rewrite teaches an agent never to touch tests at all, which is the opposite of
what this gate wants.

# Not built

`deps`, and the coverage and test-count ratchets, are specified in `plan.md` and
referenced by `profiles/flutter-android.yml`, but no code exists for them. The
profile's `gates:` block is still data nothing reads.

# See also

- [Longhaul](/product/overview.md) — what exists and what does not
- [Agent roles](agent-roles.md) — the Reviewer, which is where judgement lives instead
