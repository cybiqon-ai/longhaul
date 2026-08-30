"""`longhaul ui` — the report, live, on localhost.

stdlib `http.server` only: no framework, no build step, no dependency. The page
is the same one `longhaul report` writes, plus an update listener.

**Binds 127.0.0.1 by default and warns loudly otherwise.** The page renders
source paths, diff-shaped output and agent errors; it is not something to expose
on a network by accident.
"""

from __future__ import annotations

import errno
import json
import mimetypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import yaml

from ..schema.plan import Plan, PlanError
from ..schema.state import State
from . import render as ui_render
from .gallery import collect

DEFAULT_PORT = 4321
POLL_INTERVAL_S = 1.0
#: Long enough to keep proxies and browsers from timing the stream out.
HEARTBEAT_S = 20.0

WATCHED = ("state.json", "plan.yaml", "ledger.jsonl")


def _stamp(root: Path) -> str:
    """A cheap fingerprint of `.longhaul/` — mtime and size of what matters."""
    parts = []
    for name in WATCHED:
        path = root / ".longhaul" / name
        try:
            stat = path.stat()
            parts.append(f"{name}:{stat.st_mtime_ns}:{stat.st_size}")
        except OSError:
            parts.append(f"{name}:-")
    return "|".join(parts)


def load(root: Path) -> tuple[Plan | None, State, list[dict], str | None]:
    from ..core import state as state_io

    path = root / ".longhaul" / "plan.yaml"
    if not path.is_file():
        return None, State(), [], f"no plan at {path}"
    try:
        plan = Plan.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")))
    except PlanError as exc:
        return None, State(), [], f"{path} is not a usable plan: {len(exc.problems)} problem(s)"
    return plan, state_io.load(root), state_io.read_ledger(root), None


def _handler(root: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "longhaul"
        sys_version = ""

        def log_message(self, fmt, *args):  # noqa: A002 - stdlib signature
            pass  # the terminal belongs to the run, not to request logs

        def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            # Nothing here should ever be embedded elsewhere.
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def _page(self, live: bool) -> bytes:
            plan, state, ledger, problem = load(root)
            if plan is None:
                return (
                    f"<!doctype html><meta charset='utf-8'>"
                    f"<title>Longhaul</title><p>{problem}</p>"
                ).encode()
            # Served locally, so link rather than embed: the browser can fetch
            # /proof/... and the page stays small however long the project runs.
            gallery = collect(root, embed=False)
            if live:
                return ui_render.render(
                    plan, state, ledger, live=True, gallery=gallery
                ).encode()
            return ui_render.render_main(plan, state, ledger, gallery).encode()

        def do_GET(self) -> None:  # noqa: N802 - stdlib signature
            route = self.path.split("?", 1)[0]
            if route == "/":
                self._send(self._page(live=True), "text/html; charset=utf-8")
            elif route == "/fragment":
                self._send(self._page(live=False), "text/html; charset=utf-8")
            elif route == "/api/summary":
                plan, state, _ledger, problem = load(root)
                body = (
                    json.dumps({"error": problem})
                    if plan is None
                    else ui_render.to_json(plan, state)
                )
                self._send(body.encode(), "application/json")
            elif route.startswith("/.longhaul/proof/"):
                self._proof(route)
            elif route == "/events":
                self._events()
            else:
                self._send(b"not found", "text/plain; charset=utf-8", 404)

        def _proof(self, route: str) -> None:
            """Serve a proof artefact, and nothing outside the proof directory."""
            proof_root = (root / ".longhaul" / "proof").resolve()
            try:
                requested = (root / unquote(route.lstrip("/"))).resolve()
                # `resolve()` collapses `..`; this is what stops the URL walking
                # out of the proof directory and serving the rest of the disk.
                requested.relative_to(proof_root)
            except (ValueError, OSError):
                self._send(b"not found", "text/plain; charset=utf-8", 404)
                return
            if not requested.is_file():
                self._send(b"not found", "text/plain; charset=utf-8", 404)
                return
            mime = mimetypes.guess_type(requested.name)[0] or "application/octet-stream"
            self._send(requested.read_bytes(), mime)

        def _events(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            last = _stamp(root)
            last_beat = time.monotonic()
            try:
                # Tell the page immediately, so a browser opened after a run
                # finished still renders current data.
                self.wfile.write(b"event: update\ndata: connected\n\n")
                self.wfile.flush()
                while not getattr(self.server, "stopping", False):
                    time.sleep(POLL_INTERVAL_S)
                    current = _stamp(root)
                    if current != last:
                        last = current
                        self.wfile.write(b"event: update\ndata: changed\n\n")
                        self.wfile.flush()
                        last_beat = time.monotonic()
                    elif time.monotonic() - last_beat > HEARTBEAT_S:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
                        last_beat = time.monotonic()
            except (BrokenPipeError, ConnectionResetError):
                pass  # the tab was closed; entirely normal

    return Handler


class Server(ThreadingHTTPServer):
    daemon_threads = True
    stopping = False


class PortInUse(RuntimeError):
    pass


def serve(root: Path, host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> Server:
    try:
        return Server((host, port), _handler(root))
    except OSError as exc:
        if exc.errno in (errno.EADDRINUSE, errno.EACCES):
            raise PortInUse(f"{host}:{port} is not available ({exc.strerror})") from exc
        raise


def run(root: Path, host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> int:
    try:
        server = serve(root, host, port)
    except PortInUse as exc:
        # 4321 is also Astro's and several other dev servers' default, so this
        # is a normal thing to hit, not a crash.
        print(f"cannot start: {exc}")
        print(f"  something else is listening. Try `longhaul ui --port {port + 1}`,")
        print("  or `longhaul ui --port 0` to let the OS pick a free one.")
        return 1
    actual = server.server_address[1]
    print(f"longhaul ui on http://{host}:{actual}")
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(
            "  ! this is not localhost. The page renders source paths, agent "
            "output and error text — do not leave it exposed."
        )
    print("  reading .longhaul/ from disk; the agent does not need to be running")
    print("  ctrl-c to stop")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        while thread.is_alive():
            thread.join(0.5)
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.stopping = True
        server.shutdown()
        server.server_close()
    return 0
