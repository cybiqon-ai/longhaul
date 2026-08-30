---
type: Concept
title: The dashboard
description: A self-contained HTML report and a stdlib http.server on :4321, with no npm and no build step — and the reason it is the project's most important marketing artifact.
resource: https://github.com/cybiqon-ai/longhaul/tree/main/src/longhaul/ui
tags: [architecture, dashboard, ui, stdlib, sse, implemented]
timestamp: 2026-08-30T00:00:00Z
---

# Overview

Two commands over one renderer. `longhaul report` writes a single self-contained
`report.html` from `.longhaul/`; `longhaul ui` serves that same page from a stdlib
`http.server.ThreadingHTTPServer` on port 4321, with live updates over SSE.

**Built.** `ui/render.py`, `ui/server.py`, `ui/redact.py` and two asset files.

# No build step, on purpose

One HTML template, one CSS file, one vanilla-JS file, shipped as package data;
charts are inline SVG. No npm, no bundler, no framework. This keeps the Python
package at exactly one runtime dependency and means a contributor can change the
dashboard without a JavaScript toolchain.

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

`GET /` is the whole page with a reconnecting `EventSource` listener;
`/fragment` is just the `<main>` body, so an update swaps content in place
rather than reloading and losing scroll position; `/api/summary` is the same
numbers as JSON; `/events` is the SSE stream.

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
