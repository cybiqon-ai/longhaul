---
okf_version: "0.1"
---

# Longhaul — Knowledge Bundle

OKF bundle for **Longhaul**, an open-source tool that takes a target file and a
deadline and ships a day's worth of planned, coded, tested, committed work every
day until the deadline — waking a human only on failure or a decision.

**The single most important fact in this bundle:** as of 30 Aug 2026 Longhaul
does not work. The repository contains a plan, schemas, a driver, one gate and a
test suite. No orchestrator, no Planner, no scheduled run has ever executed.
Everything described here as a *role* is a specification, not an implementation.

This bundle documents the project only. It carries no information about the
organisation that maintains it.

# Product

* [Longhaul](product/overview.md) - what it is, what actually exists today, and what it is deliberately not.

# Architecture

* [Architecture](architecture/) - the agent roles, the gates that contain no model, the seam to Claude, and the dashboard.

# Reading notes

This bundle records what is built separately from what is designed, because the
two are very far apart right now and a document that blurred them would be worse
than none. `plan.md` at the repository root is the design; this bundle is the
state.
