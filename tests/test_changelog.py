"""Every commit hash in the changelog names a commit that exists.

Twenty-four of them did not. Each entry was written with the hash of the commit
as first made, and the changelog was then amended into that commit, which gives
it a new hash. A commit cannot contain its own hash, so the newest entry says
`pending` and the next commit fills it in.
"""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ENTRY = re.compile(r"^- \*\*`([0-9a-f]{7,40}|pending)`", re.M)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def test_every_changelog_hash_is_a_commit_on_this_branch():
    shallow = _git("rev-parse", "--is-shallow-repository")
    if shallow.returncode != 0 or shallow.stdout.strip() != "false":
        pytest.skip("needs the full history; CI checks out one commit")
    hashes = ENTRY.findall((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    assert hashes, "the changelog has no entries this test can read"
    missing = [
        h for h in hashes
        if h != "pending" and _git("merge-base", "--is-ancestor", h, "HEAD").returncode != 0
    ]
    assert missing == [], f"not commits on this branch: {missing}"
    assert hashes.count("pending") <= 1, "only the newest entry may be pending"
