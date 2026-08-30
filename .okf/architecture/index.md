# Architecture

How Longhaul is meant to work. Almost none of this is built yet — each concept
says which parts exist.

* [Agent roles](agent-roles.md) - twelve roles, four of them scoped for v0.1, none of them implemented.
* [Gates](gates.md) - deterministic diff checks with no model in the loop. The cheat detector is the one thing here that actually runs.
* [The Claude driver](driver.md) - why Longhaul shells out to the user's own CLI instead of embedding the Agent SDK.
* [The dashboard](dashboard.md) - a self-contained HTML report and a stdlib server, with no build step.
