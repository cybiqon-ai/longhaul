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


def read(root: Path | None = None) -> tuple[int | None, int | None]:
    """(pid, pgid) recorded by the holder, or (None, None)."""
    path = (root or Path.cwd()) / LOCK_PATH
    if not path.is_file():
        return None, None
    parts = path.read_text().split()
    pid = int(parts[0]) if parts and parts[0].isdigit() else None
    pgid = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    return pid, pgid


def group_is_alive(pgid: int | None) -> bool:
    """Whether any process remains in the group, orphaned children included."""
    if not pgid:
        return False
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


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
        # Both, because the orchestrator alone is not what needs killing: an
        # agent subprocess outlives a SIGTERM'd parent and keeps spending with no
        # ceiling watching it. The group is the unit of work.
        handle.write(f"{os.getpid()}\n{os.getpgid(0)}\n")
        handle.flush()
        yield path
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()
