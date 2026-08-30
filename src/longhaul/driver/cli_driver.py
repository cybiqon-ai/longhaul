"""Drive the user's own `claude` binary as a subprocess.

Longhaul deliberately does not implement authentication. The user installs
Claude Code and authenticates it themselves, with `ANTHROPIC_API_KEY` or a token
from `claude setup-token`; Longhaul only reads the environment. Anthropic's
Agent SDK terms do not permit a third-party product to offer claude.ai login.

Driving the CLI rather than the SDK also buys three things for free:
`--output-format json` returns a `session_id` and `total_cost_usd`,
`--json-schema` turns an agent's output into a validated contract, and the run
bills against the user's own subscription.
"""

from __future__ import annotations

import json
import subprocess
import time
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
        argv = [self.binary, "-p", req.prompt, "--output-format", "json"]
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
        except subprocess.TimeoutExpired:
            return AgentResult(
                ok=False,
                text="",
                duration_s=time.monotonic() - started,
                exit_code=124,
                error=f"timed out after {request.timeout_s}s",
            )

        elapsed = time.monotonic() - started
        payload = self._parse(proc.stdout)

        if payload is None:
            # No parseable JSON means the run never really started. Exit code 0
            # here has historically been mistaken for success.
            return AgentResult(
                ok=False,
                text=proc.stdout.strip(),
                duration_s=elapsed,
                exit_code=proc.returncode,
                error=f"no JSON on stdout (exit {proc.returncode}): {proc.stderr.strip()[:400]}",
            )

        error = payload.get("error") or payload.get("subtype")
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
        )

    @staticmethod
    def _parse(stdout: str) -> dict[str, Any] | None:
        stdout = stdout.strip()
        if not stdout:
            return None
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
