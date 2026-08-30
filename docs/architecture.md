# Architecture

The authoritative design document is [`plan.md`](../plan.md) at the repository
root — it carries the full reasoning, the agent-role table, the contracts, and
the staging. This page is the short orientation for someone reading the code.

## The shape

```
target.md → Planner → .longhaul/plan.yaml → Orchestrator (once per day)
                                                  ↓
              Designer → Coder → DevOps → Gates → Proof → Reviewer → Git Ops
                                                  ↓
                                     state, ledger, devlog, notification
```

One task per day, one task at a time. Not a swarm.

## Where things live

| Path | What |
|---|---|
| `src/longhaul/cli.py` | The command surface |
| `src/longhaul/core/` | Orchestrator, state I/O, supervisor, the shared command layer |
| `src/longhaul/driver/` | The seam to Claude. `cli_driver.py` shells out to `claude -p` |
| `src/longhaul/roles/` | Agent prompts, as markdown, shipped as package data |
| `src/longhaul/gates/` | Deterministic diff checks. **No model runs in here** |
| `src/longhaul/profiles/` | Per-stack commands, as YAML data |
| `src/longhaul/ui/` | The dashboard: a static renderer plus a stdlib server |
| `src/longhaul/schema/` | The `plan.yaml` and `state.json` contracts |
| `tools/` | Vendored Apache-2.0 tooling — not covered by this repo's MIT licence |

## Two invariants

**State lives on disk, in the target repository, in the open.** `.longhaul/` is
human-readable and committed. There is no database and no hidden state. Kill a
run and the next one resumes from what is on disk. Every decision Longhaul made
is readable in `git log`.

**Gates are deterministic.** Anything in `gates/` must be testable by handing it
a crafted diff and asserting the outcome. The moment a check needs judgement it
moves into the Reviewer role, where its opinion is advisory and logged rather
than load-bearing.

## Why the CLI and not the Agent SDK

Driving `claude -p --output-format json` returns a `session_id` and
`total_cost_usd` on every call — the cost ledger and cross-day session resume come
free — and `--json-schema` turns an agent's output into a validated contract
instead of parsed prose. It also runs on the user's own subscription, which is
what makes a fourteen-day unattended run affordable.

`driver/base.py` exists so an SDK driver can be added later without the
orchestrator noticing.
