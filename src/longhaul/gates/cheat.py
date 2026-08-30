"""The cheat detector.

The dominant failure of a long-running coding agent is not writing bad code. It
is making the *gate* pass instead of making the *code* work: deleting a failing
test, marking it skipped, loosening the lint config, or editing the CI workflow
that would have caught it. Every one of those produces a green run and a broken
project, and none of them is visible in a status line.

So this gate reads the diff and blocks the moves themselves. It is the product's
thesis in one file, and it is the same rule the rest of this codebase follows:
report a count, not a status.
"""

from __future__ import annotations

import re

from .base import Finding, GateResult

#: Files whose relaxation is always suspicious, mapped to a human explanation.
CONFIG_FILES = (
    "pyproject.toml",
    "setup.cfg",
    "ruff.toml",
    ".ruff.toml",
    "tsconfig.json",
    "eslint.config.js",
    "eslint.config.mjs",
    ".eslintrc",
    "analysis_options.yaml",
    "pytest.ini",
    "tox.ini",
    ".flake8",
    "mypy.ini",
)

#: Paths whose **modification** needs a human. Editing the workflow that runs the
#: tests is the most efficient way to make the tests stop mattering.
#:
#: Creating one of these where none existed is a different act and is allowed —
#: a task whose acceptance criteria say "CI ships a debug APK" cannot satisfy
#: them without writing a workflow. The first live run blocked exactly that, on
#: a brand-new file, which is a gate that stops legitimate work rather than
#: cheating. Adding a check is building the gate; changing one is lowering it.
#: Weakening a *new* workflow is still caught: `continue-on-error: true` is
#: matched on any added line, wherever it appears.
PROTECTED = (
    ".github/workflows/",
    ".longhaul/config.yml",
    ".pre-commit-config.yaml",
)

SKIP_MARKERS = (
    re.compile(r"@pytest\.mark\.(skip|xfail)"),
    re.compile(r"\bunittest\.skip\b"),
    re.compile(r"\b(it|test|describe)\.(skip|only)\s*\("),
    re.compile(r"\bxit\s*\(|\bxdescribe\s*\("),
    re.compile(r"@(Ignore|Disabled)\b"),
    re.compile(r"\bt\.Skip\s*\("),
    re.compile(r"#\[ignore\]"),
    re.compile(r"\bskip:\s*true\b"),
)

#: Swallowing an error on one line.
SWALLOWED_ERROR = (
    re.compile(r"^\s*except[^:]*:\s*pass\s*$"),
    re.compile(r"^\s*catch\s*\([^)]*\)\s*\{\s*\}\s*$"),
    re.compile(r"^\s*catch\s*\{\s*\}\s*$"),
    re.compile(r"continue-on-error:\s*true"),
)

#: ...and across two, which is the form people actually write. Both lines have
#: to be *added* for this to fire, so pre-existing handlers are left alone.
SWALLOWED_OPENERS = (
    re.compile(r"^\s*except\b[^:]*:\s*$"),
    re.compile(r"^\s*catch\s*(\([^)]*\))?\s*\{\s*$"),
    re.compile(r"^\s*rescue\b.*$"),
)
SWALLOWED_BODIES = (
    re.compile(r"^\s*pass\s*$"),
    re.compile(r"^\s*\}\s*$"),
    re.compile(r"^\s*(#|//).*$"),  # a comment where handling should be
    re.compile(r"^\s*end\s*$"),
)

TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec)/|(_test|\.test|\.spec|_spec)\.[a-z]+$")
TEST_FUNC = re.compile(r"^\s*(def test_|async def test_|func Test|it\(|test\(|void test)")


def _hunks(diff: str) -> list[tuple[str, bool, list[tuple[str, int]]]]:
    """Split a unified diff into (path, is_new, [(line, lineno), ...]) for added lines."""
    files: list[tuple[str, bool, list[tuple[str, int]]]] = []
    path: str | None = None
    added: list[tuple[str, int]] = []
    is_new = was_new = False
    lineno = 0
    for raw in diff.splitlines():
        if raw.startswith("--- "):
            is_new = raw[4:].strip() in ("/dev/null", "a//dev/null")
        elif raw.startswith("+++ "):
            if path is not None:
                files.append((path, was_new, added))
            target = raw[4:].strip()
            path = target[2:] if target.startswith(("a/", "b/")) else target
            was_new = is_new
            added = []
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            lineno = int(m.group(1)) if m else 0
        elif raw.startswith("+") and not raw.startswith("+++"):
            added.append((raw[1:], lineno))
            lineno += 1
        elif not raw.startswith("-"):
            lineno += 1
    if path is not None:
        files.append((path, was_new, added))
    return files


def _removed_by_file(diff: str) -> dict[str, list[str]]:
    removed: dict[str, list[str]] = {}
    path = None
    for raw in diff.splitlines():
        if raw.startswith("--- "):
            target = raw[4:].strip()
            path = target[2:] if target.startswith(("a/", "b/")) else target
            removed.setdefault(path, [])
        elif raw.startswith("-") and not raw.startswith("---") and path:
            removed[path].append(raw[1:])
    return removed


class CheatGate:
    name = "cheat"

    def check(self, diff: str) -> GateResult:
        result = GateResult(gate=self.name)
        added = _hunks(diff)
        removed = _removed_by_file(diff)
        result.checked = len(added)

        for path, is_new, lines in added:
            if path == "/dev/null":
                continue

            if not is_new and any(path.startswith(p) or p in path for p in PROTECTED):
                result.findings.append(
                    Finding(
                        self.name,
                        "block",
                        "protected path changed — this needs a human, not an agent",
                        path,
                    )
                )

            for index, (text, lineno) in enumerate(lines):
                for pattern in SKIP_MARKERS:
                    if pattern.search(text):
                        result.findings.append(
                            Finding(
                                self.name,
                                "block",
                                f"test disabled rather than fixed: {text.strip()[:80]}",
                                path,
                                lineno,
                            )
                        )
                        break

                swallowed = any(p.search(text) for p in SWALLOWED_ERROR)
                if not swallowed and any(p.match(text) for p in SWALLOWED_OPENERS):
                    following = lines[index + 1][0] if index + 1 < len(lines) else ""
                    swallowed = bool(following) and any(
                        p.match(following) for p in SWALLOWED_BODIES
                    )
                if swallowed:
                    result.findings.append(
                        Finding(
                            self.name,
                            "block",
                            f"error swallowed silently: {text.strip()[:80]}",
                            path,
                            lineno,
                        )
                    )

        # Net, not gross. A rewrite that removes four tests and adds five is not
        # a suite that tests less — and blocking it teaches the agent to avoid
        # touching tests at all, which is the opposite of what this gate wants.
        added_tests = {
            path: sum(1 for text, _ in lines if TEST_FUNC.search(text))
            for path, _is_new, lines in added
        }
        for path, gone in removed.items():
            if path == "/dev/null" or not TEST_PATH.search(path):
                continue
            deleted = sum(1 for line in gone if TEST_FUNC.search(line))
            net = deleted - added_tests.get(path, 0)
            if net > 0:
                result.findings.append(
                    Finding(
                        self.name,
                        "block",
                        f"{net} more test(s) removed than added ({deleted} out, "
                        f"{added_tests.get(path, 0)} in) — a suite that tests less "
                        "is not progress",
                        path,
                    )
                )

        for path, gone in removed.items():
            if any(path.endswith(cfg) for cfg in CONFIG_FILES) and gone:
                result.findings.append(
                    Finding(
                        self.name,
                        "warn",
                        "lint/type configuration changed — confirm it got stricter, not looser",
                        path,
                    )
                )

        return result
