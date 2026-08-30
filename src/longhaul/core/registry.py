"""Which projects exist on this machine.

Longhaul is a local tool: there is no server, no account, and no database. But a
home screen that lists your projects needs to know what they are, so a small
registry lives at `~/.longhaul/projects.json` — outside any repository, because
it is about this machine rather than about any one project.

The registry is a convenience index, never a source of truth. Every entry is
re-read from the project's own `.longhaul/` on load, and an entry whose directory
has gone is reported as missing rather than quietly dropped: a project that
vanished is something you want to be told about.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

REGISTRY_DIR = Path(os.environ.get("LONGHAUL_HOME", str(Path.home() / ".longhaul")))
REGISTRY_PATH = REGISTRY_DIR / "projects.json"

SLUG = re.compile(r"[^a-z0-9]+")


def slug_for(path: Path) -> str:
    """A stable, URL-safe id derived from the directory name."""
    base = SLUG.sub("-", path.name.lower()).strip("-")
    return base or "project"


@dataclass
class Project:
    id: str
    path: Path
    name: str = ""
    added_at: str = ""

    @property
    def exists(self) -> bool:
        return (self.path / ".longhaul").is_dir()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "path": str(self.path),
            "name": self.name or self.path.name,
            "added_at": self.added_at,
        }


@dataclass
class Registry:
    projects: list[Project] = field(default_factory=list)

    def get(self, project_id: str) -> Project | None:
        return next((p for p in self.projects if p.id == project_id), None)

    def unique_id(self, path: Path) -> str:
        base = slug_for(path)
        taken = {p.id for p in self.projects if p.path != path}
        if base not in taken:
            return base
        # Two repos can share a directory name; disambiguate with the parent
        # rather than a meaningless counter.
        parent = SLUG.sub("-", path.parent.name.lower()).strip("-")
        candidate = f"{parent}-{base}" if parent else f"{base}-2"
        n = 2
        while candidate in taken:
            candidate = f"{base}-{n}"
            n += 1
        return candidate


def load() -> Registry:
    if not REGISTRY_PATH.is_file():
        return Registry()
    try:
        raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupt index must not stop the tool working on the project you are
        # standing in. It is rebuilt by re-registering.
        return Registry()
    projects = [
        Project(
            id=str(entry.get("id", "")),
            path=Path(str(entry.get("path", ""))),
            name=str(entry.get("name", "")),
            added_at=str(entry.get("added_at", "")),
        )
        for entry in raw.get("projects", [])
        if entry.get("id") and entry.get("path")
    ]
    return Registry(projects=projects)


def save(registry: Registry) -> Path:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(
        {"projects": [p.to_dict() for p in registry.projects]}, indent=2
    )
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(body + "\n", encoding="utf-8")
    tmp.replace(REGISTRY_PATH)
    return REGISTRY_PATH


def register(path: Path, name: str = "") -> Project:
    """Idempotent: registering the same directory twice updates it."""
    path = path.resolve()
    registry = load()
    existing = next((p for p in registry.projects if p.path == path), None)
    if existing:
        if name:
            existing.name = name
        save(registry)
        return existing

    project = Project(
        id=registry.unique_id(path),
        path=path,
        name=name,
        added_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
    )
    registry.projects.append(project)
    save(registry)
    return project


def forget(project_id: str) -> bool:
    """Remove from the index. Never touches the project itself."""
    registry = load()
    before = len(registry.projects)
    registry.projects = [p for p in registry.projects if p.id != project_id]
    if len(registry.projects) == before:
        return False
    save(registry)
    return True
