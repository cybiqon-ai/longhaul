"""The seam between Longhaul and whatever runs the agent.

There is exactly one implementation today (`cli_driver.CliDriver`, which drives
the user's own `claude` binary). The interface exists so an Agent SDK driver can
land later without the orchestrator noticing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentResult:
    """One agent invocation.

    `cost_usd` and `session_id` come straight from `claude --output-format json`.
    `session_id` is what lets a retry resume the failed conversation with the
    error in context, instead of re-reading the whole repository.
    """

    ok: bool
    text: str
    structured: dict[str, Any] | None = None
    session_id: str | None = None
    cost_usd: float = 0.0
    duration_s: float = 0.0
    exit_code: int = 0
    error: str | None = None
    raw_events: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class AgentRequest:
    prompt: str
    role: str
    cwd: str
    allowed_tools: list[str] = field(default_factory=list)
    append_system_prompt: str | None = None
    json_schema: dict[str, Any] | None = None
    resume_session: str | None = None
    model: str | None = None
    max_turns: int | None = None
    timeout_s: int = 1800
    #: Where to write the raw event stream. The transcript is what makes a
    #: run auditable after the fact rather than a number in a ledger.
    transcript_path: str | None = None


class AgentDriver(Protocol):
    def run(self, request: AgentRequest) -> AgentResult: ...
