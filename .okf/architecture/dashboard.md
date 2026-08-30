---
type: Concept
title: The dashboard
description: A self-contained HTML report and a stdlib http.server on :4321, with no npm and no build step — and the reason it is the project's most important marketing artifact.
resource: https://github.com/cybiqon-ai/longhaul/tree/main/src/longhaul/ui
tags: [architecture, dashboard, ui, nextjs, sse, implemented]
timestamp: 2026-08-30T00:00:00Z
---

# Overview

Two commands over one renderer. `longhaul report` writes a single self-contained
`report.html` from `.longhaul/`; `longhaul ui` serves that same page from a stdlib
`http.server.ThreadingHTTPServer` on port 4321, with live updates over SSE.

**Built.** `ui/render.py`, `ui/server.py`, `ui/redact.py` and two asset files.

# Two surfaces, one API

**The application** is Next.js 16, React 19, Tailwind 4, TanStack Table and
Recharts, statically exported and **committed into the Python wheel**. A user
runs `uv tool install longhaul-ai` and has the interface: no Node, no npm, no
build step. Contributors need a JavaScript toolchain; users never do. CI builds
it and fails if the committed export is stale.

Routes: `/` lists every project on this machine; `/p/<id>` carries Overview,
Timeline, Tasks, Agent runs, **Chats**, Spend, Proof and Risks. Chats reads a
stored transcript back as a conversation, with its tool calls, their results and
any API retries the CLI recovered from.

**The report** is `longhaul report` — still one self-contained HTML file with
its data embedded, for a CI artefact or an email attachment. The server falls
back to it when no export is bundled, so a source checkout works before anyone
runs a frontend build.

# One renderer, two delivery mechanisms

`ui/data.py` assembles a single JSON payload. `longhaul report` **embeds** it in
the document; `longhaul ui` serves the shell and the browser **fetches** it from
`/api/data`, refreshing over SSE. `ui/assets/app.js` renders from that payload
either way.

That is what lets a single file be fully interactive with no network at all —
filters, sorting, the trace table and every view work from a `file://` URL, a CI
artefact, or an email attachment. It also means there is one implementation of
each view rather than a server-rendered copy and a client-rendered copy, which
would drift until one of them lied.

# Three bugs the tests could not have caught

Worth recording together, because each was invisible to the layer below it.

**The whole interface rendered unstyled.** Every utility was written
`bg-[--color-panel]` — Tailwind 3 arbitrary-value syntax. Tailwind 4 does not
error on it, it *silently generates nothing*. Build succeeded, stylesheet emitted
and linked, typecheck clean, 396 tests green, CI green — and the page referenced
classes that did not exist. Fixed by using the utilities `@theme` already
generates. `tests/test_static_export.py` now checks the **built** export, because
the source looked correct throughout.

**Then the Projects page rendered 232px wide.** The shell applied
`md:grid-cols-[232px_1fr]` unconditionally, and that page has no sidebar, so its
only child landed in the sidebar's column. Every class was correct; a stylesheet
check says nothing about the layout it produces. Found by looking at a
screenshot — which is the argument the [Proof gate](proving-it.md) makes about
other people's projects, landing on this one.

**The export was not reproducible.** Next randomises a build id per build and
bakes it into every path, so an identical rebuild produced a 55-file diff and
CI's staleness check could never pass. The id is now a hash of the source.

# The views

An application shell — sidebar, top bar, dense tables — rather than a report.

| View | What it answers |
|---|---|
| Overview | Where is this, and is anything waiting on me? |
| Timeline | Every day 1..N, so slack shows as slack rather than being closed up |
| Tasks | Filter and sort every task; expand one for criteria, diff, PR, errors |
| Agent runs | Every invocation from `ledger.jsonl` — role, attempt, duration, cost, session |
| Spend | Cost per day, and per role |
| Proof | The gallery — what each day actually produced |
| Risks | What the Planner flagged up front |

**Agent runs is the trace table.** `ledger.jsonl` is append-only and already
records one line per invocation, so the view that answers "what did it actually
do, and what did that cost" needed no new plumbing.

The pattern is proven by OKF's own `okf_visualize.py`, which produces a
self-contained interactive graph exactly this way.

# Why it matters more than it looks

For an open-source project the dashboard **is the README screenshot**. A timeline
of fourteen green days with a game screenshot under each is the most persuasive
artifact this project can produce, and the proof gallery is the view that does
that work.

It is also how the orchestrator gets debugged: reading `state.json` by hand stops
being viable around day three. That is why `report` is scoped into v0.1 rather
than left until v0.5 with the rest of the UI.

# What it serves

`GET /` is the shell; `/api/data` is the whole payload; `/api/summary` is the
headline numbers; `/events` is the SSE stream; `/.longhaul/proof/...` serves
artefacts. An update re-fetches the payload and re-renders in place, so scroll
position and the open row survive.

The server watches the mtime and size of `state.json`, `plan.yaml` and
`ledger.jsonl` and pushes an `update` event when any changes — so the browser
never polls. It also emits one on connect, so a tab opened after a run finished
still renders current data. The client backs off exponentially to 30s on
disconnect: the orchestrator restarting is normal, and hammering a socket that
is not there is not.

# Nothing reaches the browser unredacted

`ui/redact.py` reuses the **secrets gate's own patterns** rather than keeping a
second list, so a pattern added for the gate protects the UI too. Agent output —
a build log, a stack trace, a rejected git push — reaches the page verbatim, and
`report.html` is a file people commit, attach to issues and screenshot. A
credential in a URL loses the credential and keeps the host, because an error
naming the remote is useful and an error naming the token is a leak.

# Design rules

- **One command layer.** `/approve` over Telegram and the Approve button in the
  dashboard call the same function in `core/commands.py`. Two front-ends, never
  two implementations — otherwise they drift and one of them lies.
- **Every write is a git diff.** Approving, skipping or editing the plan writes
  into the committed `.longhaul/`, so the history of human interventions is in
  the repository rather than in hidden state.
- **Binds 127.0.0.1 only.** The page renders source, diffs and agent output.
  Exposing it requires an explicit `--host` and prints a warning, and streamed
  output is secret-redacted server-side before it reaches the browser.
- **Works with the agent stopped.** It renders from disk, so it is equally a live
  monitor and a post-mortem — and `report --static` can publish a run to GitHub
  Pages.

# See also

- [Longhaul](/product/overview.md) — what exists and what does not
- [Agent roles](agent-roles.md) — what produces the state the dashboard renders
