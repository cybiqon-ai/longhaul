# longhaul

Read `plan.md` first. It is the design document and the real specification; this
repository is a scaffold against it, and most of what `plan.md` describes is not
built yet. `.okf/` records what actually runs versus what is only designed —
check it before assuming a component exists.

## This repo is public

Everything here is world-readable and every commit is attributed. Never commit a
secret, a token, a customer name, or anything about the organisation that
maintains the project. If a fact is about a company rather than about Longhaul,
it does not belong in this repository.

## House rules for the code

- **Report a count, not a status.** Anything that can fail silently prints how
  many things it actually did. Exit code 0 has meant "did nothing" often enough
  that it cannot be trusted on its own. This is not just a style preference here
  — it is the product's whole thesis, and `src/longhaul/gates/` is that thesis
  applied to an agent.
- **Gates contain no model.** Everything in `src/longhaul/gates/` is
  deterministic and testable from a crafted diff. A check that needs judgement
  belongs in the Reviewer role, where its opinion is advisory and logged. A gate
  that can be argued with is not a gate.
- **stdlib first.** `pyyaml` is the only runtime dependency, and it is there
  because `plan.yaml` needs a parser. A second one needs a reason written into
  the PR.
- **One command layer.** An action offered in both the dashboard and Telegram is
  implemented once, in `core/commands.py`. Two front-ends, never two
  implementations — they drift, and then one of them lies.
- **Nothing writes outside `.longhaul/` and the task worktree** without an
  explicit reason. This tool runs unattended inside other people's repositories.
- Every scheduled entrypoint gets `flock` and `timeout`, and logs to a directory
  that already exists.

## Knowledge bundle (`.okf/`)

This repo carries an OKF knowledge bundle at `.okf/` — a graph of markdown
concepts describing how the system actually works, including the parts that are
broken or unbuilt. Start at `.okf/index.md`.

**Keep it in sync in the same pass as the code**, without being asked. Triggers:
a new, removed or renamed module; a schema change; an architectural decision; a
changed schedule or deploy flow; or discovering that something documented is
wrong.

1. Edit the affected concept body **and** its `timestamp`; fix cross-links; add
   a concept for a genuinely new component; mark removed things with a
   `**Deprecation**` note rather than deleting the context.
2. Refresh the relevant `index.md` and append a dated entry to `.okf/log.md`.
3. Validate before finishing:

   ```bash
   python3 tools/okf_validate.py .okf --strict
   ```

Skip trivial changes. When unsure whether something is substantive, err toward a
short note in `log.md`.

## Before you finish

```bash
pytest && ruff check . && python3 tools/okf_validate.py .okf --strict
```
