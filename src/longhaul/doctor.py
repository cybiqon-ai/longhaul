"""Preflight checks.

Run before day 1 and before *every* scheduled run. The single most important
check here is that the `claude` CLI is still authenticated: an expired session
prints an error and exits in a way that has already been mistaken for success in
production, costing four consecutive nights of a scheduled pipeline. Longhaul
treats that as a hard, loud failure.

Reports a count, not a status.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

TIMEOUT_S = 60


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    fatal: bool = True

    @property
    def mark(self) -> str:
        return "✓" if self.ok else ("✗" if self.fatal else "!")


def _which(binary: str) -> str | None:
    return shutil.which(binary)


def check_claude_installed() -> Check:
    path = _which("claude")
    if path is None:
        return Check("claude installed", False, "not on PATH — see https://claude.com/claude-code")
    return Check("claude installed", True, path)


def check_claude_authenticated() -> Check:
    """Actually round-trip the CLI. Presence on PATH proves nothing.

    We ask for a one-word answer with no tools. A logged-out CLI reports the
    failure as the *result* on stdout while still being easy to mistake for a
    successful run, so an empty or error-shaped result is treated as failure.
    """
    if _which("claude") is None:
        return Check("claude authenticated", False, "skipped — claude not installed")

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")):
        detail = "no ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN in the environment"
        return Check("claude authenticated", False, detail)

    try:
        proc = subprocess.run(
            ["claude", "--bare", "-p", "Reply with the single word: ok"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return Check("claude authenticated", False, f"no response in {TIMEOUT_S}s")

    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        return Check("claude authenticated", False, f"exit {proc.returncode}: {out[:200]}")
    if not out:
        return Check("claude authenticated", False, "empty response — treat as logged out")
    lowered = out.lower()
    if any(s in lowered for s in ("session expired", "not authenticated", "please run", "login")):
        return Check("claude authenticated", False, f"auth error in result: {out[:200]}")
    return Check("claude authenticated", True, "round-tripped a prompt")


def check_git_identity() -> Check:
    try:
        name = subprocess.run(
            ["git", "config", "user.name"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
        email = subprocess.run(
            ["git", "config", "user.email"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Check("git identity", False, str(exc))
    if not name or not email:
        return Check("git identity", False, "user.name or user.email is unset")
    return Check("git identity", True, f"{name} <{email}>")


def check_binary(binary: str, *, fatal: bool = True) -> Check:
    path = _which(binary)
    return Check(f"{binary}", path is not None, path or "not on PATH", fatal=fatal)


def run(profile_binaries: list[str] | None = None, *, quick: bool = False) -> list[Check]:
    """Run the checks. `quick` skips the network round-trip to Claude."""
    checks = [check_claude_installed()]
    if not quick:
        checks.append(check_claude_authenticated())
    checks.append(check_git_identity())
    checks.extend(check_binary(b) for b in (profile_binaries or []))
    return checks


def report(checks: list[Check]) -> int:
    """Print the checks and return a process exit code."""
    for c in checks:
        print(f"  {c.mark} {c.name}: {c.detail}")
    passed = sum(1 for c in checks if c.ok)
    failed = [c for c in checks if not c.ok and c.fatal]
    warned = sum(1 for c in checks if not c.ok and not c.fatal)
    print(f"\nchecks: {len(checks)}  passed: {passed}  failed: {len(failed)}  warnings: {warned}")
    return 1 if failed else 0
