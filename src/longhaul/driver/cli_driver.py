"""Drive the user's own `claude` binary as a subprocess.

Longhaul deliberately does not implement authentication. The user installs
Claude Code and authenticates it themselves, with `ANTHROPIC_API_KEY` or a token
from `claude setup-token`; Longhaul only reads the environment. Anthropic's
Agent SDK terms do not permit a third-party product to offer claude.ai login.

Output is read as `--output-format stream-json`, which gives everything the
single-JSON form did — `session_id`, `total_cost_usd`, `structured_output` — and
additionally the whole conversation, one event per line. That transcript is what
makes a run auditable after the fact rather than a number in a ledger, and it is
persisted verbatim so nothing is lost to a summariser.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from .base import AgentRequest, AgentResult

# Error categories that arrive on `system/api_retry` events. A 429 is the
# scheduler's problem, not the task's: it must not consume a retry budget.
TRANSIENT = {"rate_limit", "overloaded", "server_error"}
AUTH_FAILURES = {"authentication_failed", "oauth_org_not_allowed", "billing_error"}


class ClaudeAuthError(RuntimeError):
    """Raised when the CLI is not usable at all. Halt loudly; never skip."""


class CliDriver:
    def __init__(self, binary: str = "claude", bare: bool = False) -> None:
        # `--bare` gives a reproducible run by skipping the host's hooks,
        # plugins, MCP servers and CLAUDE.md — but it also refuses to read the
        # subscription login, so it is opt-in rather than the default.
        self.binary = binary
        self.bare = bare

    def _argv(self, req: AgentRequest) -> list[str]:
        argv = [self.binary, "-p", req.prompt, "--output-format", "stream-json", "--verbose"]
        if self.bare:
            argv.append("--bare")
        # Deny anything not explicitly allowed. Never --dangerously-skip-permissions:
        # this runs unattended against a real repository.
        argv += ["--permission-mode", "dontAsk"]
        if req.allowed_tools:
            argv += ["--allowedTools", ",".join(req.allowed_tools)]
        if req.json_schema is not None:
            argv += ["--json-schema", json.dumps(req.json_schema)]
        if req.resume_session:
            argv += ["--resume", req.resume_session]
        if req.append_system_prompt:
            argv += ["--append-system-prompt", req.append_system_prompt]
        if req.model:
            argv += ["--model", req.model]
        if req.max_turns is not None:
            argv += ["--max-turns", str(req.max_turns)]
        return argv

    def run(self, request: AgentRequest) -> AgentResult:
        started = time.monotonic()
        try:
            proc = subprocess.run(
                self._argv(request),
                cwd=request.cwd,
                capture_output=True,
                text=True,
                timeout=request.timeout_s,
            )
        except FileNotFoundError as exc:
            raise ClaudeAuthError(f"{self.binary} is not on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            self._persist(request, (exc.stdout or b"").decode("utf-8", "replace")
                          if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
            return AgentResult(
                ok=False,
                text="",
                duration_s=time.monotonic() - started,
                exit_code=124,
                error=f"timed out after {request.timeout_s}s",
            )

        elapsed = time.monotonic() - started
        self._persist(request, proc.stdout)
        events = self._events(proc.stdout)
        payload = self._result_of(events)

        if payload is None:
            # No result event means the run never really started. Exit code 0
            # here has historically been mistaken for success.
            return AgentResult(
                ok=False,
                text=proc.stdout.strip()[-2000:],
                duration_s=elapsed,
                exit_code=proc.returncode,
                error=f"no result event (exit {proc.returncode}): {proc.stderr.strip()[:400]}",
                raw_events=events,
            )

        error = payload.get("error") or (
            payload.get("subtype") if payload.get("subtype") != "success" else None
        )
        if error in AUTH_FAILURES:
            raise ClaudeAuthError(f"claude is not authenticated: {error}")

        is_error = bool(payload.get("is_error")) or proc.returncode != 0
        return AgentResult(
            ok=not is_error,
            text=payload.get("result", "") or "",
            structured=payload.get("structured_output"),
            session_id=payload.get("session_id"),
            cost_usd=float(payload.get("total_cost_usd") or 0.0),
            duration_s=elapsed,
            exit_code=proc.returncode,
            error=str(error) if is_error and error else None,
            raw_events=events,
        )

    @staticmethod
    def _persist(request: AgentRequest, stdout: str) -> None:
        """Write the transcript verbatim. Never let this break the run."""
        if not request.transcript_path or not stdout:
            return
        try:
            path = Path(request.transcript_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(stdout, encoding="utf-8")
        except OSError:
            pass  # a full disk must not lose the work, only the record of it

    @staticmethod
    def _events(stdout: str) -> list[dict[str, Any]]:
        """Every parseable line.

        The CLI interleaves non-JSON lines — a stdin warning, for instance — so
        an unparseable line is skipped rather than treated as the end of output.
        """
        events = []
        for line in (stdout or "").splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                events.append(parsed)
        return events

    @staticmethod
    def _result_of(events: list[dict[str, Any]]) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.get("type") == "result":
                return event
        return None

    @staticmethod
    def retries(events: list[dict[str, Any]]) -> list[str]:
        """Transient API failures the CLI recovered from, for the ledger.

        A run that succeeded after three 429s cost wall-clock that is otherwise
        invisible, and a run that is retrying is not a run that is stuck.
        """
        return [
            str(e.get("error"))
            for e in events
            if e.get("type") == "system" and e.get("subtype") == "api_retry"
        ]
