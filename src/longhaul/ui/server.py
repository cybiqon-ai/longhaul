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
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import yaml

from ..schema.plan import Plan, PlanError
from ..schema.state import State
from . import api as ui_api
from . import render as ui_render
from .data import build

DEFAULT_PORT = 4321

PROJECT_ROUTE = re.compile(r"^/p/(?!_(?:/|$))[^/]+(?P<rest>/.*)?$")


def _rewrite_project_route(route: str) -> str:
    """`/p/neon-drift/tasks` → `/p/_/tasks`, the file the export actually made."""
    match = PROJECT_ROUTE.match(route)
    if not match:
        return route
    rest = match.group("rest") or ""
    return f"/p/_{rest}"


#: The statically exported Next.js app, bundled into the wheel at release time.
#: Absent in a source checkout until `cd web && npm run build`, in which case the
#: zero-dependency fallback page is served instead — the tool still works.
STATIC_DIR = Path(__file__).parent / "static"
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

        def _page(self) -> bytes:
            plan, _state, _ledger, problem = load(root)
            if plan is None:
                return (
                    "<!doctype html><meta charset='utf-8'>"
                    f"<title>Longhaul</title><p>{problem}</p>"
                ).encode()
            # The shell only. Data arrives from /api/data and refreshes over
            # SSE, so the page never reloads and the served document stays small
            # however long the project runs.
            return ui_render.shell(plan.project, None).encode()

        def _data(self) -> bytes:
            plan, state, ledger, problem = load(root)
            if plan is None:
                return json.dumps({"error": problem}).encode()
            # Link rather than embed: served locally the browser fetches them.
            payload = build(plan, state, ledger, root=root, embed=False, live=True)
            return json.dumps(payload).encode()

        def do_GET(self) -> None:  # noqa: N802 - stdlib signature
            route = unquote(self.path.split("?", 1)[0])

            if route == "/api/projects":
                self._json(ui_api.projects())
            elif route.startswith("/api/projects/"):
                self._project_api(route[len("/api/projects/"):])
            elif route == "/api/data":
                self._send(self._data(), "application/json")
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
            elif STATIC_DIR.is_dir():
                self._static(route)
            elif route == "/":
                self._send(self._page(), "text/html; charset=utf-8")
            else:
                self._send(b"not found", "text/plain; charset=utf-8", 404)

        def _json(self, body: dict, status: int = 200) -> None:
            self._send(json.dumps(body).encode(), "application/json", status)

        def _project_api(self, rest: str) -> None:
            parts = [p for p in rest.split("/") if p]
            if not parts:
                self._json({"error": "not found"}, 404)
                return
            project_id = parts[0]
            if len(parts) == 1:
                body = ui_api.project_data(project_id)
            elif parts[1] == "transcript" and len(parts) > 2:
                body = ui_api.project_transcript(project_id, "/".join(parts[2:]))
            elif parts[1] == "summary":
                body = ui_api.summary(project_id)
            else:
                body = {"error": "not found"}
            self._json(body, 404 if body.get("error") == "not found" else 200)

        def _static(self, route: str) -> None:
            """Serve the exported app.

            A static export prerenders `/p/[id]` as `/p/_`, so there is no file
            for `/p/neon-drift/tasks`. Serving index.html there would hand back
            the *home* page, which is why the project routes are rewritten onto
            their `_` equivalent instead — the client reads the real id from the
            URL. Anything else that is not an asset falls back to index.html.
            """
            route = _rewrite_project_route(route)
            candidate = (STATIC_DIR / route.lstrip("/")).resolve()
            try:
                candidate.relative_to(STATIC_DIR.resolve())
            except ValueError:
                self._send(b"not found", "text/plain; charset=utf-8", 404)
                return

            # Order matters. The export writes both `p/_.html` (the page) and
            # `p/_/` (a directory holding its subroutes), so resolving the
            # directory first would serve neither.
            if not candidate.is_file():
                sibling = candidate.with_suffix(".html")
                if candidate.suffix == "" and sibling.is_file():
                    candidate = sibling
                elif candidate.is_dir() and (candidate / "index.html").is_file():
                    candidate = candidate / "index.html"

            if not candidate.is_file():
                if "." in route.rsplit("/", 1)[-1]:  # a missing asset, not a route
                    self._send(b"not found", "text/plain; charset=utf-8", 404)
                    return
                candidate = STATIC_DIR / "index.html"
            if not candidate.is_file():
                self._send(self._page(), "text/html; charset=utf-8")
                return

            mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            self._send(candidate.read_bytes(), mime)

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
