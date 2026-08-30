"""`longhaul init` — make a repository ready, and refuse if it is not.

Onboarding is where an unattended tool earns or loses trust. The failure this
avoids is discovering on day 4 that the Android SDK was never installed, or that
the remote is unwritable, after four days of work exist on a branch.

Writes nothing outside `.longhaul/` and `.gitignore`, and never overwrites a file
that already exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .. import profiles
from ..schema.config import CONFIG_PATH
from . import registry

#: One copy, shipped as package data. A second copy at the repository root
#: would drift from it, and a template that has drifted is documentation
#: that lies.
TEMPLATES = Path(__file__).resolve().parents[1] / "templates"

#: Worktrees and raw transcripts are generated and large; the rest of
#: `.longhaul/` is meant to be committed — that is the whole point.
GITIGNORE_LINES = (
    "# Longhaul: generated per-run artefacts. The rest of .longhaul/ is",
    "# intended to be committed — plan, state and ledger are the audit trail.",
    ".longhaul/worktrees/",
    ".longhaul/runs/",
    ".longhaul/lock",
)


@dataclass
class InitResult:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def ensure_gitignore(root: Path, result: InitResult) -> None:
    path = root / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if ".longhaul/worktrees/" in existing:
        result.skipped.append(".gitignore (already covers .longhaul)")
        return
    block = "\n".join(GITIGNORE_LINES)
    separator = "" if not existing or existing.endswith("\n") else "\n"
    path.write_text(f"{existing}{separator}\n{block}\n", encoding="utf-8")
    result.created.append(".gitignore (appended)")


def write_config(root: Path, profile: str, result: InitResult) -> None:
    path = root / CONFIG_PATH
    if path.is_file():
        result.skipped.append(f"{CONFIG_PATH} (already exists)")
        return
    body = _template("config.yml").replace(
        "profile: flutter-android", f"profile: {profile}", 1
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    result.created.append(str(CONFIG_PATH))


def write_target(root: Path, target: Path, result: InitResult) -> None:
    if target.is_file():
        result.skipped.append(f"{target} (already exists)")
        return
    target.write_text(_template("target.md"), encoding="utf-8")
    result.created.append(f"{target} — fill this in before planning")


def write_schedule(root: Path, kind: str, profile: str, result: InitResult) -> None:
    """Scheduling is opt-in and written as a file you read before installing."""
    if kind == "none":
        return
    files = {
        "cron": (".longhaul/cron.txt", "cron.txt"),
        "systemd": (".longhaul/longhaul.timer", "longhaul.timer"),
        "actions": (".github/workflows/longhaul.yml", "longhaul-workflow.yml"),
    }
    if kind not in files:
        result.problems.append(f"unknown schedule {kind!r}; use cron, systemd or actions")
        return
    rel, template = files[kind]
    path = root / rel
    if path.is_file():
        result.skipped.append(f"{rel} (already exists)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _template(template).replace("{{PROJECT_DIR}}", str(root)), encoding="utf-8"
    )
    result.created.append(f"{rel} — read it before installing")


def run(
    root: Path,
    *,
    profile: str,
    target: Path,
    schedule: str = "none",
    is_repo: bool = True,
) -> InitResult:
    result = InitResult()

    if not is_repo:
        result.problems.append(
            "not a git repository — longhaul works in worktrees, so run `git init` first"
        )
        return result
    if profile not in profiles.available():
        result.problems.append(
            f"unknown profile {profile!r}; available: {', '.join(profiles.available())}"
        )
        return result

    write_config(root, profile, result)
    write_target(root, target, result)
    ensure_gitignore(root, result)
    write_schedule(root, schedule, profile, result)

    # Index it so `longhaul ui` can list it from anywhere. The registry is a
    # convenience, never a source of truth — the project's own .longhaul/ is.
    project = registry.register(root)
    result.created.append(f"registered as project '{project.id}'")
    return result
