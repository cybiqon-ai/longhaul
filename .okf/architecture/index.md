# Architecture

How Longhaul is meant to work. Almost none of this is built yet — each concept
says which parts exist.

* [Agent roles](agent-roles.md) - twelve roles; Planner, Coder and DevOps built, nine to go.
* [The plan contract](plan-contract.md) - plan.yaml, and why it is validated hard rather than trusted.
* [The day loop](the-day-loop.md) - one task a day, isolated in a worktree, and safe to kill at any point.
* [Shipping](shipping.md) - commit, push, open a PR, and prove a CI run actually started.
* [Supervision](supervision.md) - ceilings, loop detection, a lock and a kill switch, all outside the agent.
* [Operating a project](operating.md) - init, report and rollback: getting ready, seeing what happened, undoing a day.
* [Notifications](notifications.md) - Telegram that never raises, and a confirmed message id as the only evidence.
* [Gates](gates.md) - deterministic diff checks with no model in the loop. The cheat detector is the one thing here that actually runs.
* [The Claude driver](driver.md) - why Longhaul shells out to the user's own CLI instead of embedding the Agent SDK.
* [The dashboard](dashboard.md) - a self-contained HTML report and a stdlib server, with no build step.
