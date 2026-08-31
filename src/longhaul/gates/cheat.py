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

#: Paths where *removing or altering* an existing line needs a human. Editing
#: the workflow that runs the tests is the most efficient way to make the tests
#: stop mattering.
#:
#: What is dangerous is **weakening** a check, not touching the file. Two live
#: runs proved the blunter rules wrong, both by blocking legitimate work:
#:
#:   1. Creating a workflow was blocked, on a task whose acceptance criteria
#:      said "CI ships a debug APK" — unsatisfiable without writing one.
#:   2. Then *adding a step* to an existing workflow was blocked, on a task
#:      required to run a new guard in CI. That diff added 8 lines and removed
#:      none: it made CI stricter, and the gate stopped it.
#:
#: So a purely additive change is allowed — it cannot remove a check — while any
#: diff that deletes or rewrites an existing line still blocks. Weakening
#: through addition is caught separately: `continue-on-error: true` and the
#: swallowed-error patterns are matched on added lines wherever they appear.
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
    re.compile(r"^\s*end\s*$"),
)

#: Comments are skipped when looking for the handler's body. An explanatory
#: comment inside an `except` is good practice, and flagging it taught nothing
#: except to stop writing comments — `except X:` followed by a comment and then
#: real handling is not a swallowed error. What matters is the first line that
#: actually does something.
COMMENT_ONLY = re.compile(r"^\s*(#|//|\*|\"\"\"|\'\'\')")

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


def _next_statement(lines: list[tuple[str, int]], start: int) -> tuple[str, bool]:
    """(next real added line, whether only comments stood before it).

    Both halves matter. A comment *followed by* handling is fine; a handler
    whose entire body is a comment is a swallowed error wearing an explanation.
    """
    saw_comment = False
    for text, _lineno in lines[start:]:
        if not text.strip():
            continue
        if COMMENT_ONLY.match(text):
            saw_comment = True
            continue
        return text, saw_comment
    return "", saw_comment


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

            protected = any(path.startswith(p) or p in path for p in PROTECTED)
            if protected and not is_new and removed.get(path):
                result.findings.append(
                    Finding(
                        self.name,
                        "block",
                        f"{len(removed[path])} line(s) removed from a protected path — "
                        "adding a check is fine, removing or rewriting one needs a human",
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
                    following, saw_comment = _next_statement(lines, index + 1)
                    if following:
                        swallowed = any(p.match(following) for p in SWALLOWED_BODIES)
                    else:
                        # Nothing but comments after the opener: the explanation
                        # is the whole handler.
                        swallowed = saw_comment
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
