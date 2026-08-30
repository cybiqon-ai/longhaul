"""Reading and writing `.longhaul/`.

Writes are atomic. A run can be killed at any moment — by a watchdog, by
SIGTERM, by a laptop lid — and a half-written `state.json` would lose the whole
project's memory, which is a much worse outcome than losing one step.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..schema.state import State

LONGHAUL_DIR = Path(".longhaul")
STATE_PATH = LONGHAUL_DIR / "state.json"
LEDGER_PATH = LONGHAUL_DIR / "ledger.jsonl"
RUNS_DIR = LONGHAUL_DIR / "runs"
WORKTREES_DIR = LONGHAUL_DIR / "worktrees"


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)  # atomic on POSIX and Windows


def load(root: Path | None = None) -> State:
    path = (root or Path.cwd()) / STATE_PATH
    if not path.is_file():
        return State()
    return State.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save(state: State, root: Path | None = None) -> Path:
    from ..schema.state import now

    state.updated_at = now()
    path = (root or Path.cwd()) / STATE_PATH
    write_atomic(path, json.dumps(state.to_dict(), indent=2, sort_keys=False) + "\n")
    return path


def append_ledger(entry: dict, root: Path | None = None) -> None:
    """One line per agent invocation. Append-only: the bill is auditable later."""
    path = (root or Path.cwd()) / LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def read_ledger(root: Path | None = None) -> list[dict]:
    path = (root or Path.cwd()) / LEDGER_PATH
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            # A torn final line from a killed run. Skip it; do not lose the rest.
            continue
    return out
