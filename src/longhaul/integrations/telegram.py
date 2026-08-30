"""Telegram, over stdlib urllib.

Two rules, both learned the hard way in the pipelines this is modelled on:

**Alerting must not be able to crash the thing it is reporting on.** `send`
never raises. A notifier that takes down the orchestrator turns a bad day into
a lost one.

**A confirmed `message_id` is the only evidence a notification landed.** An HTTP
200 with `ok: false`, a wrong chat id, a bot removed from a channel — all of
those look like success from the caller's side unless the id is checked.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

API = "https://api.telegram.org"
#: Telegram rejects anything longer; truncate on a line break, never mid-word.
MSG_LIMIT = 4096


@dataclass(frozen=True)
class Sent:
    ok: bool
    message_id: int | None = None
    error: str | None = None


def credentials() -> tuple[str | None, str | None]:
    return (
        os.environ.get("TELEGRAM_TOKEN") or os.environ.get("LONGHAUL_TELEGRAM_TOKEN"),
        os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("LONGHAUL_TELEGRAM_CHAT_ID"),
    )


def truncate(text: str, limit: int = MSG_LIMIT) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    head, _, _ = cut.rpartition("\n")
    return (head or cut) + "…"


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send(text: str, *, timeout: int = 20) -> Sent:
    """Never raises. Returns whether Telegram confirmed a message id."""
    token, chat_id = credentials()
    if not token or not chat_id:
        return Sent(False, error="TELEGRAM_TOKEN or TELEGRAM_CHAT_ID is not set")

    body = json.dumps(
        {
            "chat_id": chat_id,
            "text": truncate(text),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
    ).encode()
    req = urllib.request.Request(
        f"{API}/bot{token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "longhaul"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read() or b"{}")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return Sent(False, error=f"{type(exc).__name__}: {exc}")

    # HTTP 200 with ok:false is the failure mode that reads as success.
    if not payload.get("ok"):
        return Sent(False, error=str(payload.get("description") or "telegram returned ok:false"))
    message_id = (payload.get("result") or {}).get("message_id")
    if not message_id:
        return Sent(False, error="telegram confirmed nothing — no message_id in the response")
    return Sent(True, message_id=int(message_id))
