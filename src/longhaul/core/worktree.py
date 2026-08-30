"""Isolated checkouts, one per task.

A worktree rather than a branch in the main checkout: a task that wedges — a
half-applied change, a merge conflict, a process killed mid-write — must not
leave the user's working tree in a state they have to untangle by hand. Longhaul
runs unattended, so "just fix it in the morning" is not available.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .state import WORKTREES_DIR


class GitError(RuntimeError):
    pass


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout.strip()


@dataclass(frozen=True)
class Worktree:
    path: Path
    branch: str
    #: The commit this task branched from. Every diff is taken against *this*,
    #: never against HEAD — see `diff()`.
    base_sha: str = ""


def branch_name(task_id: str) -> str:
    return f"longhaul/{task_id}"


def create(task_id: str, root: Path | None = None, base: str = "HEAD") -> Worktree:
    """Make (or re-attach to) the worktree for a task. Idempotent."""
    root = root or Path.cwd()
    path = root / WORKTREES_DIR / task_id
    branch = branch_name(task_id)

    if path.is_dir():
        return Worktree(path=path, branch=branch, base_sha=merge_base(path, root))

    path.parent.mkdir(parents=True, exist_ok=True)
    base_sha = git("rev-parse", base, cwd=root)
    existing = git("branch", "--list", branch, cwd=root)
    args = ["worktree", "add", str(path)]
    args += [branch] if existing else ["-b", branch, base]
    git(*args, cwd=root)
    return Worktree(path=path, branch=branch, base_sha=base_sha)


def merge_base(worktree: Path, root: Path) -> str:
    """Where this worktree diverged from the main line, for re-attached trees."""
    head = git("rev-parse", "HEAD", cwd=root, check=False)
    return git("merge-base", "HEAD", head, cwd=worktree, check=False) or head


def remove(task_id: str, root: Path | None = None, force: bool = False) -> bool:
    """Detach the worktree, leaving the branch. Returns whether anything went."""
    root = root or Path.cwd()
    path = root / WORKTREES_DIR / task_id
    if not path.exists():
        return False
    args = ["worktree", "remove", str(path)]
    if force:
        args.insert(2, "--force")
    git(*args, cwd=root)
    return True


def diff(worktree: Path, base: str) -> str:
    """Everything this task has changed since `base`, for the gates to read.

    `base` is the commit the worktree branched from, **never `HEAD`**. If the
    Coder commits its own work — and a real one did, on the first live run — then
    HEAD moves and a HEAD-relative diff is empty. The gates would see nothing and
    wave the change through. That is a gate bypass, so the base is pinned when
    the worktree is created and every diff is taken against it.
    """
    tracked = git("diff", base, cwd=worktree, check=False)
    untracked = git("ls-files", "--others", "--exclude-standard", cwd=worktree, check=False)
    parts = [tracked] if tracked else []
    for name in filter(None, untracked.splitlines()):
        # /dev/null headers make new files legible to the same diff parser.
        body = git("diff", "--no-index", "/dev/null", name, cwd=worktree, check=False)
        if body:
            parts.append(body)
    return "\n".join(parts)


def is_repo(root: Path | None = None) -> bool:
    try:
        return git("rev-parse", "--is-inside-work-tree", cwd=root or Path.cwd()) == "true"
    except (GitError, FileNotFoundError):
        return False
