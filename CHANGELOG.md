# Changelog

Every commit, with what it actually did. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project is
pre-1.0 and does not yet publish releases, so everything sits under Unreleased.

Entries record what was found as well as what was built — several of the fixes
below exist because running the thing for real broke it, and that is the most
useful part of the history to a reader.

## [Unreleased]

### 2026-08-30

- **`48c001e` feat(ui): an application, not a report.** Rebuilt as a proper
  shell — sidebar navigation, top bar, dense sortable and filterable tables —
  after a Langfuse screenshot made clear the previous page read as a printout
  rather than a tool. Seven views: Overview, Timeline, Tasks, **Agent runs**,
  Spend, Proof, Risks.
  Agent runs is the trace table, and it needed no new plumbing:
  `ledger.jsonl` is append-only and already records one line per invocation, so
  role, attempt, duration, cost and session id were already there.
  Architecturally the important part is that `ui/data.py` builds **one** payload
  and `app.js` is the **only** renderer. `longhaul report` embeds the payload;
  `longhaul ui` serves the shell and fetches it. A single file therefore stays
  fully interactive with no network — filters, sorting and every view work from
  `file://` — and there is no server-rendered copy of a view to drift from the
  client-rendered one.
  Still no npm, no bundler, no framework, and still exactly one runtime
  dependency. Charts are inline SVG.

- **`1485b50` feat(assets): licence provenance as a gate, not paperwork.** The
  Assets role prefers generating over sourcing — a generated asset has no licence
  question, no attribution and no supply chain — and never takes anything whose
  licence it cannot state. `gates/provenance.py` blocks any newly added image,
  font or audio file with no row in `assets/CREDITS.md`. Build outputs, vendored
  directories and `.longhaul/proof/` screenshots are not shipped assets and are
  ignored.
  An application pulled from a store over an unlicensed font is pulled for the
  licence, not for the font, and months later the only record is what was written
  down at the time.
  **This completes v0.3.**

- **`b1ddab9` feat(gallery): every day's proof in one strip, and a second
  profile.** The gallery is the most persuasive thing this tool produces —
  fourteen screenshots of an application visibly appearing, one per day, each
  something you can look at rather than a number you have to trust. In
  `report.html` images are embedded as data URIs so the page stays genuinely
  self-contained; above a per-image and a whole-page budget they are linked
  instead, and the page says which, because a 40MB file nobody can open is not
  better than a link. The live server links rather than embeds and serves them
  from `/.longhaul/proof/`, with path-traversal protection proven by tests
  (including percent-encoded attempts) rather than assumed.
  Adds the `nextjs-web` profile — partly to be useful, partly to keep the
  profile mechanism honest: anything hard-coded for Flutter shows up the moment
  a genuinely different stack is described in the same shape. Its proof serves
  the real build and photographs the page, because `npm run build` passing is not
  evidence the page loads.

- **`4ad3a0c` feat(proof): does it actually run?** Tests passing is not evidence
  an application works — a Flutter app can compile, lint clean and pass every
  test while showing a grey screen. Each task declares what proof means, the
  profile says how to produce it, and the artefact lands in
  `.longhaul/proof/day-NN/` where a human can look. The Inspector then judges the
  artefact against the day's criteria and the design system, with read-only tools
  so it cannot alter what it is judging.
  **A proof step that could not run is not a pass**, and is reported separately
  from one that ran and failed. Steps that exit 0 and leave no artefact are also
  not a pass.
  *Found by wiring it in:* the flutter profile started with `adb
  wait-for-device`, which blocks forever with nothing attached — it hung the
  entire test suite. Replaced with `adb get-state`, every profile's proof is now
  time-bounded, and a test asserts no shipped profile uses a blocking primitive.
  *Then found by running it for real:* with `adb` installed but no device, the
  result read **FAILED**, which would burn a retry budget on every developer
  machine without an emulator. Profiles now separate `requires:` from `steps:` —
  a failed precondition means this machine cannot demonstrate anything, which is
  a different fact from the change being broken.

- **`3a126dd` feat(designer): a design system, and `needs_human` that actually
  does the work.** The Designer role produces one tokens document — palette roles
  with contrast ratios, type scale, spacing scale, motion, tone — plus the
  implementation file the code imports, because a design system that exists only
  as markdown is a document, not a system. Where the author reserved the choice
  it produces at least three named options, marks exactly one PROVISIONAL so
  implementation is not blocked, and never quietly promotes it.
  *Found by reading the real 14-day plan:* every `needs_human` task's acceptance
  criteria ask for **the material the decision rests on** — three palette
  options, a dependency comparison, a difficulty curve. Parking with nothing
  produced nothing to decide from and blocked every dependent behind an empty
  question, which stalled the reference project on **day 2 of 14**. Such tasks
  now run, commit their artefacts, and *then* park for the decision. Dependents
  still wait, which is the conservative and correct default.

- **`66d0b72` feat(ui): the report, live on localhost.** `longhaul ui` serves it
  from stdlib `http.server` on `:4321` with SSE — no framework, no build step,
  still one runtime dependency. The server watches `.longhaul/` and pushes; the
  browser never polls, and swaps the `<main>` body rather than reloading so
  scroll position survives. `/api/summary` returns the same numbers as JSON.
  Localhost only, `X-Frame-Options: DENY`, and an explicit warning if you bind
  elsewhere.
  Credentials are redacted before anything reaches a browser, **reusing the
  secrets gate's own patterns** rather than a second list — agent output reaches
  the page verbatim, and `report.html` is a file people commit and screenshot.
  *Found immediately on the first real run:* port 4321 was already held by an
  unrelated dev server and `ui` crashed with a raw `OSError` traceback. It is
  also Astro's default port, so this is normal rather than exceptional; it now
  names the port and suggests `--port`.
  *Also found, by running `longhaul gate` on this diff:* the cheat gate treated
  a comment as a swallowed-error body, so `except PortInUse: # explanation` +
  real handling was blocked. Flagging that teaches an agent to stop writing
  comments, which is the opposite of the intent. It now looks past comments to
  the first line that actually does something — while a handler whose *entire*
  body is a comment still blocks, because that is an explanation standing in for
  handling.
  This completes v0.2 — every command in the roadmap through v0.2 now ships, and
  the placeholder machinery that made unimplemented commands exit 2 is gone.

- **`91c97cb` feat(rollback): undo a day, with checkpoints to undo it to.**
  Every completed task now leaves an annotated git tag, and `longhaul rollback N`
  puts the repository back to the last checkpoint before day N, returning that
  day's tasks and everything after to `pending` so the next run genuinely retries
  them. Dry by default — `--apply` is required, because it is destructive by
  definition. Rolling back day 1 is refused: there is no checkpoint before the
  first day, and silently discarding a repository is not a one-word operation.
  Tags are never moved, so re-running a finished day cannot shift a checkpoint
  someone may already have rolled back to.

- **`82bad72` feat(report): a self-contained HTML page from `.longhaul/`.**
  `longhaul report` writes one file with the CSS inlined and zero external
  resources, so it opens from `file://`, from a CI artifact, or on a machine that
  never ran the agent — equally a live monitor and a post-mortem. `--json` prints
  the same numbers as data. Every task with its acceptance criteria, why anything
  failed or is waiting, PR links, risk flags, light and dark.
  *Found by rendering the real project:* the header said `tasks: 17` while the
  buckets summed to 16 — an `in_progress` task was in no bucket at all. A summary
  whose parts do not add up to the whole is the failure this project is named
  for. Every status is now reported, with a parametrised test asserting the
  counts reconcile against the task total.
  *Also found by a test:* the page hid the reason a task was **parked**, which is
  precisely the task a human has to act on.

- **`0c884f4` feat(init): prepare a repository, and refuse if it is not ready.**
  `longhaul init` writes `.longhaul/config.yml`, a `target.md` skeleton and the
  right `.gitignore` lines, then runs `doctor` and prints the next four commands.
  It never overwrites an existing file and is idempotent. `--schedule
  cron|systemd|actions` also writes a scheduling file for you to read before
  installing — each carrying the house rules (`flock`, `timeout`, a log directory
  that exists) and, for Actions, the warning that a push with the default
  `GITHUB_TOKEN` means your CI never runs.
  The `.gitignore` block excludes only `worktrees/`, `runs/` and `lock`:
  `plan.yaml`, `state.json` and the ledger are the audit trail and belong in the
  repository.
  *Noted while writing it:* templates briefly existed in two places, which is the
  same drift hazard as a config template that no longer matches the code. There
  is now one copy, shipped as package data.

- **`b4c516c` fix(kill): signal the process group, not just the orchestrator.**
  Killing the parent alone orphans the agent it spawned — verified directly:
  SIGTERM to a parent, and its child survives reparented to init. For this tool
  that means a `claude -p` still running and still spending with no ceiling
  watching it, which quietly undermines every limit added in the previous commit.
  The lock now records the pgid alongside the pid, `kill` signals the group, and
  it refuses to clear the lock while the group still has members.

- **`ed24cee` feat(supervisor,notify): ceilings, loop detection, a lock, and a
  Telegram digest.** The last pieces before this is safe to leave on a cron.
  `.longhaul/config.yml` with conservative defaults (`auto_merge: false`, and no
  supported way to change it); project/daily/per-task cost ceilings and an
  attempt budget, all enforced outside the agent; `flock` so a scheduled run
  cannot overlap itself; `longhaul kill`; a `halted` status distinct from
  `failed`. A Telegram notifier that never raises and treats a confirmed
  `message_id` as the only evidence a message landed, sending a digest that
  reports counts rather than a status.
  *Found while writing it:* the loop detector normalised every number out of an
  error before fingerprinting, so `expected 1, got 2` and `expected 3, got 4`
  looked identical — an agent making real progress would have been halted as a
  loop. Over-normalising is worse than under-normalising here: a missed loop
  costs one retry, a false loop costs the task.
  *Also:* a test that compared a value to itself, which is coverage-shaped and
  proves nothing, rewritten to actually check the shipped config template against
  the code's defaults.

- **`1c8c71e` feat(gitops): commit, push, open a PR — and prove CI actually
  ran.** `core/gitops.py` plus a stdlib-`urllib` GitHub client. Conventional
  commit derived from the task, PR body listing the acceptance criteria and which
  gates ran, `--no-push` to stay local, PR links surfaced in `longhaul status`.
  **Auto-merge does not exist.**
  The load-bearing part is `verify_ci_started`: GitHub does not trigger workflows
  on commits pushed with the default `GITHUB_TOKEN`, so a pipeline that pushes
  with it gets green PRs and a CI system that never ran. Absence of a run is
  treated as a failure with a named cause, distinguished from a repo that has no
  workflows. `wait_for_ci` returns the job count too, because a run can conclude
  `success` having executed nothing.
  *Found while writing it:* a test written `assert "ghp_" not in msg or
  "example.com" in msg` passed on its second clause while the token was echoed in
  full — and the redaction it was supposed to cover did not exist. A test with an
  `or` in its assertion usually asserts nothing. Both fixed.

- **`dc3a033` feat(gates): scan every diff for credentials before anything is
  pushed.** `gates/secrets.py` blocks GitHub/Anthropic/OpenAI/AWS/Google/Slack/
  Stripe/Telegram tokens, private keys, credentials embedded in URLs, generic
  secret-looking assignments, and any committed `.env`. Placeholders and
  interpolation holes still pass so docs and examples work. Wired into the day
  loop and into `longhaul gate` alongside the cheat gate.
  It lands *before* the push machinery on purpose: push is the point of no
  return, and rewriting history does not un-leak a token.
  *Found while writing it:* the first version of these tests contained realistic
  credential literals and **GitHub push protection rejected the push** — the
  correct call, since a scanner's own fixtures are the likeliest hiding place for
  a real secret. Every fixture is now assembled by concatenation, so no complete
  credential string exists in any source file. A `# longhaul: allow-secret`
  pragma covers fixtures that genuinely need a credential shape, and every use
  emits a warning rather than being honoured silently.
  *Also found, by running `longhaul gate` on this very diff:* the cheat gate
  counted deleted test functions without counting added ones, so a net-positive
  rewrite was blocked. Now measured net per file — blocking a rewrite teaches an
  agent never to touch tests, the opposite of the intent.

- **`ad4db06` feat(orchestrator): run a day's work — and close a gate bypass
  found by doing it.** `longhaul run` and `longhaul status`: pick the next
  eligible task, isolate it in a git worktree, let the Coder implement it, gate
  the diff, build and test deterministically, record state atomically. Idempotent
  and resumable, both tested. DevOps implemented deterministically rather than as
  an agent.
  *Found by the first live run:* the Coder committed its own work, so a
  HEAD-relative diff was empty and **the cheat gate examined nothing** — 761
  insertions invisible. Diffs are now taken against a base commit pinned at
  worktree creation. Also: the protected-path rule blocked a *new* CI workflow on
  a task that required writing one, so creating a workflow is now distinguished
  from modifying one.

- **`c07d4b2` feat(planner): the first role that exists as code rather than a
  spec.** `longhaul plan` and `longhaul simulate`. `schema/plan.py` validates the
  contract hard — no acceptance criteria, a dependency on a later day, cycles,
  unknown deps, duplicate ids — and reports every problem rather than the first.
  The Planner gets read-only tools, asserted by a test.
  *Found by running it:* `doctor` required an API-key env var and so failed on a
  machine whose `claude` was logged in on a subscription; and it round-tripped
  through `--bare`, which never reads OAuth, so it was testing a different
  credential path from the driver.

- **`86e6102` fix(ci): the workflow YAML never parsed, and nothing noticed.** The
  first push produced a red run with **zero jobs and no logs** — a `: ` inside a
  plain YAML scalar made the file invalid, in the Lint step that prints how many
  findings ruff produced. `tests/test_workflows.py` now parses every workflow and
  asserts it defines jobs and a trigger.

- **`8f24b43` Scaffold Longhaul: the plan, and the parts of it that already
  run.** The design in `plan.md`, plus a CLI surface, `doctor`, a subprocess
  driver for `claude -p`, and the cheat detector. Corrections to the original
  notes: no claude.ai login (SDK terms), `longhaul.dev`/`.sh` are taken, and PyPI
  `longhaul` is taken so the distribution is `longhaul-ai`.
