---
type: Concept
title: Proving it
description: Design system, assets with licence provenance, and the Proof gate — the parts that make "day 7 is done" mean something you can look at.
resource: https://github.com/cybiqon-ai/longhaul/tree/main/src/longhaul/gates/proof.py
tags: [architecture, proof, design, assets, provenance, implemented]
timestamp: 2026-08-30T00:00:00Z
---

# Overview

**Built**, and together these complete v0.3. Tests passing is not evidence an
application works: a Flutter app can compile, lint clean and pass every unit
test while showing a grey screen. If a fortnight of unattended work is going to
mean anything, "day 7 is done" has to be something a person can look at.

# The Proof gate, and its third state

Each task declares what proof means, the profile says how to produce it, the
artefact lands in `.longhaul/proof/day-NN/`, and the **Inspector** — read-only
tools, so it cannot alter what it judges — decides whether it shows what the day
claims. Its prompt lists the failures a passing suite happily coexists with: a
grey screen, a framework placeholder, a debug banner, a stack trace, a spinner
where content was expected. It is told a false pass is the expensive one.

The distinction that took two attempts to get right: **could-not-run is a third
state, not a failure.**

- A missing *binary* was caught from the start.
- `adb` installed with **no device attached** was not, and read as FAILED —
  which would burn a retry budget on every developer machine without an emulator
  running. Profiles now separate `requires:` from `steps:`.

Steps that exit 0 and leave no artefact are also not a pass. That is the same
shape as a suite that runs zero tests.

# The primitive that hung everything

The flutter profile opened with `adb wait-for-device`, which blocks forever when
nothing is attached. Wiring proof into the day loop hung the **entire test
suite**. It is `adb get-state` now, every profile's proof is time-bounded, and a
test asserts no shipped profile uses a blocking primitive.

# needs_human runs the work

Reading the real fourteen-day plan showed every `needs_human` task's acceptance
criteria asking for **the material the decision rests on** — three palette
options, a dependency comparison, a difficulty curve, three icon options.
Parking such a task without running it produced nothing to decide from and
blocked every dependent behind an empty question: on the reference plan, that
stalled the project on **day 2 of 14**.

So `needs_human` now means a human must *decide*, not that no work happens. The
task runs, commits its artefacts, and then parks with them waiting. Dependents
stay blocked, which is the conservative and correct default.

# Provenance is a gate, not paperwork

An application pulled from a store over an unlicensed font is pulled for the
licence, not for the font, and months later the only thing anyone has is what
was written down at the time. `gates/provenance.py` blocks any newly added
image, font or audio file that has no row in `assets/CREDITS.md`. Build outputs,
vendored directories and `.longhaul/proof/` screenshots are not shipped assets
and are ignored.

The Assets role is told to prefer generating over sourcing — a generated asset
has no licence question, no attribution and no supply chain — and never to take
anything whose licence it cannot state.

# The gallery

Every day's artefact in one strip. For an open-source project it is the most
persuasive thing here: fourteen screenshots of an application visibly appearing,
one per day. `report.html` embeds images as data URIs so it opens from a CI
artefact with nothing else alongside; above a per-image and a whole-page budget
they are linked instead and the page says which. The live server links and
serves them itself, with path-traversal protection proven by tests including
percent-encoded attempts.

# See also

- [The day loop](the-day-loop.md) — where proof runs
- [Gates](gates.md) — the deterministic checks it sits alongside
- [The dashboard](dashboard.md) — where the gallery is rendered
