# Writing a target file

`target.md` is the only thing you write. Everything else is derived from it.

It is read once, by the Planner, and turned into a dependency-ordered task graph
with acceptance criteria per day. Its quality sets the ceiling on everything
downstream: a vague target produces a plausible plan and fourteen days of
plausible commits.

## What to include

**What you are building, in one paragraph.** Written for someone who has never
heard of it. If you cannot describe it without a diagram, it is probably two
projects.

**What "done" looks like.** Concretely. "Installable APK, five levels, no
crashes on a cold start" beats "a polished game."

**Constraints that are not negotiable.** The stack, the platform, a package name,
a dependency you must or must not use, a licence you have to respect. The Planner
will honour these; it will invent them if you don't.

**What is explicitly out of scope.** This is the highest-value section and the
one people skip. It is how you stop the agent gold-plating on day 9.

**Decisions you want to make yourself.** Anything you list here becomes a
`needs_human` flag in the plan and parks rather than guesses.

## What to leave out

Implementation detail. File layouts, class names, and function signatures written
in advance mostly get contradicted by day 4 and then argued with for ten days.
Describe the outcome and the constraints; let the plan own the structure.

## Example

See [`examples/android-game/target.md`](../examples/android-game/target.md) — a
real fourteen-day target for a Flutter game, including its out-of-scope list.

## After you write it

```bash
longhaul init --target target.md --days 14 --profile flutter-android
longhaul simulate     # read the plan before you commit two weeks to it
```

`simulate` runs the Planner only. Read the fourteen days it proposes. If day 9 is
vague, the target was vague about day 9 — fix the target and re-plan, which is
much cheaper than finding out on day 9.
