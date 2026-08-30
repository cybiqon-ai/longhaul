"""Does it actually run?

Tests passing is not evidence an application works. A Flutter app can compile,
lint clean and pass every unit test while showing a grey screen; a web app can do
the same while failing to boot. The whole premise of shipping unattended for a
fortnight is that "day 7 is done" means something, and a green test suite does
not carry that weight on its own.

So every task declares what proof means, the profile says how to produce it, and
the artefact lands in `.longhaul/proof/day-NN/` where a human can look at it.

**A proof step that could not run is not a pass.** That distinction is the whole
point of this file: `ran=False` is reported separately from `ok=False`, and
neither is success.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Per *step*, not per task. `adb wait-for-device` with nothing attached blocks
#: forever, so this is the difference between a slow run and a hung one. A
#: profile can raise it with `proof.timeout_s` when a step genuinely needs longer.
DEFAULT_STEP_TIMEOUT_S = 120

#: `{artifacts.apk}`, `{proof_dir}`, `{package}` and friends.
PLACEHOLDER = re.compile(r"\{([a-z_]+(?:\.[a-z_]+)?)\}")


@dataclass
class ProofResult:
    kind: str = ""
    #: Did the steps execute at all? A missing emulator means `ran=False`.
    ran: bool = False
    #: Did they succeed? Only meaningful when `ran`.
    ok: bool = False
    artifacts: list[Path] = field(default_factory=list)
    detail: str = ""
    steps_run: int = 0
    log: str = ""

    @property
    def passed(self) -> bool:
        return self.ran and self.ok

    def summary(self) -> str:
        if not self.kind:
            return "no proof declared"
        if not self.ran:
            return f"proof '{self.kind}' could not run: {self.detail}"
        state = "ok" if self.ok else "FAILED"
        return f"proof '{self.kind}' {state} · {self.steps_run} step(s) · {self.detail}"


def _substitute(command: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context:
            return str(context[key])
        head, _, tail = key.partition(".")
        nested = context.get(head)
        if isinstance(nested, dict) and tail in nested:
            return str(nested[tail])
        return match.group(0)  # leave an unknown placeholder visible

    return PLACEHOLDER.sub(replace, command)


def _run(command: str, cwd: Path, timeout_s: int) -> tuple[int, str, float]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout_s
        )
        code, output = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        code, output = 124, f"timed out after {timeout_s}s"
    return code, output, time.monotonic() - started


def missing_tools(profile: dict[str, Any]) -> list[str]:
    """Binaries the proof steps need that are not on PATH."""
    spec = profile.get("proof") or {}
    needed = set()
    for step in list(spec.get("requires") or []) + list(spec.get("steps") or []):
        first = step.strip().split()[0] if step.strip() else ""
        if first and not first.startswith(("{", "sleep")):
            needed.add(first)
    return sorted(b for b in needed if shutil.which(b) is None)


def run(
    profile: dict[str, Any],
    worktree: Path,
    proof_dir: Path,
    *,
    package: str = "",
    timeout_s: int = DEFAULT_STEP_TIMEOUT_S,
) -> ProofResult:
    spec = profile.get("proof") or {}
    timeout_s = int(spec.get("timeout_s") or timeout_s)
    result = ProofResult(kind=str(spec.get("kind", "")))

    if not result.kind:
        result.detail = "the profile declares no proof step"
        return result

    steps = spec.get("steps") or []
    if not steps:
        result.detail = f"proof kind '{result.kind}' declares no steps to run"
        return result

    absent = missing_tools(profile)
    if absent:
        # Honest, and distinct from failing: nothing was demonstrated either way.
        result.detail = f"missing on this machine: {', '.join(absent)}"
        return result

    proof_dir.mkdir(parents=True, exist_ok=True)
    context = {
        "proof_dir": proof_dir,
        "package": package,
        "artifacts": profile.get("artifacts") or {},
    }

    # Preconditions separate "this machine cannot demonstrate it" from "the
    # change is broken". An installed `adb` with no device attached is the
    # former: failing the task there would burn a retry budget on every
    # developer machine without an emulator running.
    for check in spec.get("requires") or []:
        command = _substitute(check, context)
        code, output, _ = _run(command, worktree, min(timeout_s, 60))
        if code != 0:
            reason = (output or "").strip().splitlines()
            result.detail = (
                f"precondition not met: `{command}`"
                + (f" — {reason[-1][:120]}" if reason else "")
            )
            return result

    result.ran = True
    logs = []
    for step in steps:
        command = _substitute(step, context)
        code, output, elapsed = _run(command, worktree, timeout_s)
        result.steps_run += 1
        logs.append(f"$ {command}\n[{code}] {elapsed:.1f}s\n{output.strip()[-2000:]}")
        if code != 0:
            result.log = "\n\n".join(logs)
            result.detail = f"step {result.steps_run} failed (exit {code}): {command}"
            return result

    result.log = "\n\n".join(logs)
    result.artifacts = sorted(p for p in proof_dir.iterdir() if p.is_file())

    if not result.artifacts:
        # Steps that exit 0 and leave nothing behind have demonstrated nothing.
        result.detail = "every step exited 0 but produced no artefact"
        return result

    result.ok = True
    result.detail = ", ".join(p.name for p in result.artifacts)
    return result
