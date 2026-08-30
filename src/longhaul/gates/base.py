"""Gate protocol.

A gate is deterministic. It takes a diff (and, where relevant, the repository
before and after) and returns findings. **No model runs inside a gate.** If a
check needs judgement it belongs in the Reviewer role instead — a gate that can
be argued with is not a gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Finding:
    gate: str
    severity: str  # "block" | "warn"
    message: str
    path: str | None = None
    line: int | None = None

    def __str__(self) -> str:
        where = self.path or "-"
        if self.line is not None:
            where = f"{where}:{self.line}"
        return f"[{self.gate}] {where} {self.message}"


@dataclass
class GateResult:
    gate: str
    findings: list[Finding] = field(default_factory=list)
    checked: int = 0  # how many things were actually examined — report a count

    @property
    def blocked(self) -> bool:
        return any(f.severity == "block" for f in self.findings)


class Gate(Protocol):
    name: str

    def check(self, diff: str) -> GateResult: ...
