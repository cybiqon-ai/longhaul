"""Read a stored run back as a conversation.

`.longhaul/runs/day-NN/<task>/<role>-<attempt>.jsonl` holds the raw event stream
exactly as the CLI emitted it. This turns that into something a person can read
— which is the difference between a ledger row saying `$1.99` and being able to
see what was actually asked and done for it.

Nothing here interprets or summarises. It reshapes, and redacts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..ui.redact import redact

#: Long tool results — a whole file, a build log — make a transcript unreadable
#: and a payload enormous. The full text is always still on disk.
MAX_BLOCK_CHARS = 4000


@dataclass
class Message:
    role: str  # "assistant" | "user" | "system" | "result"
    text: str = ""
    tools: list[dict[str, Any]] = field(default_factory=list)
    #: Set when the message came from a subagent rather than the main thread.
    parent_tool_use_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "tools": self.tools,
            "subagent": bool(self.parent_tool_use_id),
        }


@dataclass
class Transcript:
    path: Path
    messages: list[Message] = field(default_factory=list)
    session_id: str | None = None
    cost_usd: float = 0.0
    duration_ms: int = 0
    num_turns: int = 0
    retries: list[str] = field(default_factory=list)
    result: str = ""
    ok: bool = True
    tools_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "cost_usd": round(self.cost_usd, 4),
            "duration_ms": self.duration_ms,
            "num_turns": self.num_turns,
            "retries": self.retries,
            "result": self.result,
            "ok": self.ok,
            "tools_used": self.tools_used,
            "messages": [m.to_dict() for m in self.messages],
        }


def _clip(text: str) -> str:
    if len(text) <= MAX_BLOCK_CHARS:
        return text
    return text[:MAX_BLOCK_CHARS] + f"\n… {len(text) - MAX_BLOCK_CHARS:,} more characters on disk"


def _blocks(content: Any) -> tuple[str, list[dict[str, Any]]]:
    """Split a message's content into readable text and tool activity."""
    if isinstance(content, str):
        return content, []
    text_parts, tools = [], []
    for block in content or []:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text":
            text_parts.append(str(block.get("text", "")))
        elif kind == "thinking":
            thought = str(block.get("thinking", "")).strip()
            if thought:
                text_parts.append(thought)
        elif kind == "tool_use":
            tools.append({
                "kind": "call",
                "name": block.get("name", ""),
                "input": _clip(json.dumps(block.get("input", {}), indent=2)),
            })
        elif kind == "tool_result":
            body = block.get("content")
            if isinstance(body, list):
                body = "".join(
                    str(b.get("text", "")) for b in body if isinstance(b, dict)
                )
            tools.append({
                "kind": "result",
                "name": "",
                "error": bool(block.get("is_error")),
                "input": _clip(str(body or "")),
            })
    return "\n\n".join(p for p in text_parts if p.strip()), tools


def read(path: Path) -> Transcript:
    transcript = Transcript(path=path)
    if not path.is_file():
        return transcript

    seen_tools: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue  # the CLI interleaves plain warnings
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue  # a torn final line from a killed run
        if not isinstance(event, dict):
            continue

        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "api_retry":
            transcript.retries.append(str(event.get("error", "unknown")))
        elif kind in ("assistant", "user"):
            message = event.get("message") or {}
            text, tools = _blocks(message.get("content"))
            for tool in tools:
                if tool["kind"] == "call" and tool["name"]:
                    seen_tools.append(tool["name"])
            if text or tools:
                transcript.messages.append(
                    Message(
                        role=kind,
                        text=redact(text),
                        tools=[{**t, "input": redact(t["input"])} for t in tools],
                        parent_tool_use_id=event.get("parent_tool_use_id"),
                    )
                )
        elif kind == "result":
            transcript.session_id = event.get("session_id")
            transcript.cost_usd = float(event.get("total_cost_usd") or 0)
            transcript.duration_ms = int(event.get("duration_ms") or 0)
            transcript.num_turns = int(event.get("num_turns") or 0)
            transcript.result = redact(str(event.get("result", "")))
            transcript.ok = not event.get("is_error")

    transcript.tools_used = sorted(set(seen_tools))
    return transcript


def path_for(root: Path, day: int, task_id: str, role: str, attempt: int) -> Path:
    return root / ".longhaul" / "runs" / f"day-{day:02d}" / task_id / f"{role}-{attempt}.jsonl"


def index(root: Path) -> list[dict[str, Any]]:
    """Every stored transcript, newest first, without reading them all."""
    runs_dir = root / ".longhaul" / "runs"
    if not runs_dir.is_dir():
        return []
    found = []
    for path in runs_dir.rglob("*.jsonl"):
        parts = path.relative_to(runs_dir).parts
        if len(parts) != 3 or not parts[0].startswith("day-"):
            continue
        role, _, attempt = path.stem.rpartition("-")
        try:
            day = int(parts[0].removeprefix("day-"))
        except ValueError:
            continue
        found.append({
            "id": str(path.relative_to(root)),
            "day": day,
            "task": parts[1],
            "role": role or path.stem,
            "attempt": int(attempt) if attempt.isdigit() else 1,
            "size": path.stat().st_size,
            "modified": path.stat().st_mtime,
        })
    found.sort(key=lambda r: (-r["modified"], r["day"]))
    return found
