"""A small GitHub client over stdlib urllib.

No `requests`, no `gh` CLI: this runs unattended on machines Longhaul does not
control, and every dependency is something that can break there.

Only what Git Ops needs — open a pull request, and answer the one question that
matters after a push: *did a CI run actually start?*
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

API = "https://api.github.com"
TOKEN_ENV = ("GITHUB_TOKEN", "GH_TOKEN", "LONGHAUL_GITHUB_TOKEN")

REMOTE = re.compile(
    r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/\s]+?)(?:\.git)?$"
)


class GitHubError(RuntimeError):
    pass


def find_token() -> str | None:
    """Environment first. `~/.git-credentials` is a fallback, not a habit."""
    for name in TOKEN_ENV:
        value = os.environ.get(name)
        if value:
            return value
    creds = Path.home() / ".git-credentials"
    if creds.is_file():
        for line in creds.read_text(encoding="utf-8").splitlines():
            # longhaul: allow-secret — this is the pattern, not a credential
            match = re.match(r"https://([^:]+):([^@]+)@github\.com", line.strip())
            if match:
                return match.group(2)
    return None


#: `user:token@host` in a remote URL. Error strings reach logs, PR bodies and
#: Telegram, so a credential must never survive into one.
CREDENTIAL_IN_URL = re.compile(r"(://)[^\s/:@]+:[^\s/@]+@")


def redact(url: str) -> str:
    return CREDENTIAL_IN_URL.sub(r"\1***:***@", url)


def parse_remote(url: str) -> tuple[str, str]:
    match = REMOTE.search(url.strip())
    if not match:
        raise GitHubError(f"not a github remote: {redact(url)}")
    return match.group("owner"), match.group("repo")


@dataclass
class PullRequest:
    number: int
    url: str
    draft: bool = False


class GitHub:
    def __init__(self, owner: str, repo: str, token: str | None = None) -> None:
        self.owner, self.repo = owner, repo
        self.token = token or find_token()
        if not self.token:
            raise GitHubError(
                "no GitHub token — set GITHUB_TOKEN, or run with --no-push to stay local"
            )

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        req = urllib.request.Request(
            f"{API}{path}",
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "longhaul",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read() or b"null")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise GitHubError(f"{method} {path} → {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise GitHubError(f"{method} {path} failed: {exc.reason}") from exc

    def open_pull_request(
        self, *, head: str, base: str, title: str, body: str, draft: bool = False
    ) -> PullRequest:
        existing = self._request(
            "GET", f"/repos/{self.owner}/{self.repo}/pulls?head={self.owner}:{head}&state=open"
        )
        if existing:
            pr = existing[0]
            return PullRequest(pr["number"], pr["html_url"], pr.get("draft", False))
        pr = self._request(
            "POST",
            f"/repos/{self.owner}/{self.repo}/pulls",
            {"head": head, "base": base, "title": title, "body": body, "draft": draft},
        )
        return PullRequest(pr["number"], pr["html_url"], pr.get("draft", False))

    def runs_for_sha(self, sha: str) -> list[dict]:
        data = self._request(
            "GET", f"/repos/{self.owner}/{self.repo}/actions/runs?head_sha={sha}"
        )
        return data.get("workflow_runs", []) if isinstance(data, dict) else []

    def get_run(self, run_id: int) -> dict:
        data = self._request("GET", f"/repos/{self.owner}/{self.repo}/actions/runs/{run_id}")
        return data if isinstance(data, dict) else {}

    def jobs_for_run(self, run_id: int) -> list[dict]:
        data = self._request(
            "GET", f"/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/jobs"
        )
        return data.get("jobs", []) if isinstance(data, dict) else []

    def has_workflows(self) -> bool:
        data = self._request("GET", f"/repos/{self.owner}/{self.repo}/actions/workflows")
        return bool(data.get("total_count")) if isinstance(data, dict) else False
