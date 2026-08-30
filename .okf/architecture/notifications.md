---
type: Concept
title: Notifications
description: Telegram over stdlib urllib, pluggable, that never raises and treats a confirmed message_id as the only evidence anything landed.
resource: https://github.com/cybiqon-ai/longhaul/tree/main/src/longhaul/core/notify.py
tags: [architecture, telegram, alerting, implemented]
timestamp: 2026-08-30T00:00:00Z
---

# Overview

**Built.** `integrations/telegram.py` sends; `core/notify.py` decides what is
said and routes it. Backends are selected in `.longhaul/config.yml`; `none` is
the default, so an unconfigured project is silent rather than broken.

# Two rules

**Alerting must not be able to crash the thing it reports on.** `send` never
raises — network failure, malformed JSON, missing credentials all come back as a
`Sent(ok=False, error=...)`. A notifier that takes down the orchestrator turns a
bad day into a lost one.

**A confirmed `message_id` is the only evidence a notification landed.** An HTTP
200 carrying `ok: false`, a wrong chat id, a bot removed from its channel — every
one of those looks like success from the caller's side unless the id is checked.
Both cases are covered by tests, because this is the shape of failure the whole
project is about: something reporting success while having done nothing.

# The digest reports a count

*"Day 4 done"* is a status. *"day 1/14 · 1 done · 0 failed · 2 parked · 0 halted ·
14 to go · spent $0.51"* is a count, and it is the difference between a digest
someone reads and one nobody does. Tasks that are parked or halted are listed
under **needs you** with the first line of their reason, and open pull requests
are linked.

Message bodies are HTML-escaped, so a stack trace cannot break the message, and
truncated on a line break at Telegram's 4096-character limit.

# Not built

Telegram *commands* — `/status`, `/pause`, `/approve`, `/skip` — are specified in
`plan.md` and would be the project's first interactive surface. They must share
one command layer with the dashboard's buttons: two front-ends, never two
implementations.

# See also

- [Supervision](supervision.md) — what produces the halts a human needs to see
- [The day loop](the-day-loop.md) — where the digest is sent from
