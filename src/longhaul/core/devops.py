"""Build, lint and test — deterministically, with no model involved.

`plan.md` lists DevOps as an agent role. It is implemented here as plain
subprocess execution instead, because running `flutter test` requires no
judgement, and asking a model whether the tests passed reintroduces exactly the
self-report this project exists to remove. Interpreting a failure *does* need
judgement, and that happens where it belongs: the raw output is fed back to the
Coder on retry.

Reports a count, not a status. A suite that ran zero tests is a failure here even
when the exit code is 0 — that has meant "did nothing" too often to be trusted.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STEP_ORDER = ("install", "lint", "test", "build")
DEFAULT_TIMEOUT_S = 1800


@dataclass
class Step:
    name: str
    command: str
    exit_code: int
    output: str
    duration_s: float

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass
class BuildReport:
    steps: list[Step] = field(default_factory=list)
    test_count: int | None = None

    @property
    def ok(self) -> bool:
        if not self.steps or any(not s.ok for s in self.steps):
            return False
        # A green suite that ran nothing is not a pass.
        return self.test_count is None or self.test_count > 0

    @property
    def failed(self) -> list[Step]:
        return [s for s in self.steps if not s.ok]

    def summary(self) -> str:
        bits = [f"{s.name} {'ok' if s.ok else 'FAILED'}" for s in self.steps]
        if self.test_count is not None:
            bits.append(f"tests {self.test_count}")
        return " · ".join(bits)

    def feedback(self, limit: int = 4000) -> str:
        """What the Coder is given on a retry: the real error, not a summary."""
        if self.ok:
            return ""
        if not self.steps:
            return "No build steps ran at all — the profile defined no commands."
        if self.test_count == 0 and not self.failed:
            return (
                "Every command exited 0 but the suite ran ZERO tests. That is a "
                "failure: the change is unverified. Add tests that actually execute."
            )
        parts = []
        for step in self.failed:
            parts.append(f"### `{step.name}` failed (exit {step.exit_code})\n"
                         f"$ {step.command}\n{step.output.strip()[-limit:]}")
        return "\n\n".join(parts)


def _run(command: str, cwd: Path, timeout_s: int) -> tuple[int, str, float]:
    import time

    started = time.monotonic()
    try:
        proc = subprocess.run(
            command, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout_s
        )
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout_s}s", time.monotonic() - started
    return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), time.monotonic() - started


def run(profile: dict[str, Any], cwd: Path, timeout_s: int = DEFAULT_TIMEOUT_S) -> BuildReport:
    commands = profile.get("commands") or {}
    report = BuildReport()

    for name in STEP_ORDER:
        command = commands.get(name)
        if not command:
            continue
        code, output, elapsed = _run(command, cwd, timeout_s)
        report.steps.append(Step(name, command, code, output, elapsed))
        if code != 0:
            break  # no point building after the tests failed

    counter = commands.get("test_count")
    if counter and not any(s.name == "test" and not s.ok for s in report.steps):
        code, output, _ = _run(counter, cwd, 300)
        if code == 0:
            match = re.search(r"\d+", output.strip().splitlines()[-1] if output.strip() else "")
            report.test_count = int(match.group()) if match else 0
        else:
            report.test_count = 0
    return report
