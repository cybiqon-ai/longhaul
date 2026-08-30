"""One run at a time.

A scheduled job that can overlap itself is a scheduled job that will, the first
time a run takes longer than its interval — and two orchestrators sharing one
`state.json` and one set of worktrees corrupt both.

`flock` releases automatically when the process dies, however it dies, which a
PID file does not.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
from collections.abc import Iterator
from pathlib import Path

LOCK_PATH = Path(".longhaul/lock")


class AlreadyRunning(RuntimeError):
    pass


@contextlib.contextmanager
def acquire(root: Path | None = None) -> Iterator[Path]:
    path = (root or Path.cwd()) / LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("w")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise AlreadyRunning(
                f"another longhaul run holds {path} — not starting a second one"
            ) from exc
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        yield path
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()
