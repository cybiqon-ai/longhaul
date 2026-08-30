"""Scan a diff for credentials before anything is pushed.

This gate exists because push is the point of no return. A token in a working
tree is a mistake; a token in a public git history is an incident, and rewriting
history does not un-leak it — it has already been cloned, cached and indexed.

Patterns are deliberately conservative: a false positive costs a human thirty
seconds, a false negative costs a credential rotation and an audit.
"""

from __future__ import annotations

import re

from .base import Finding, GateResult

#: (name, pattern). Anchored on the issuer prefix wherever one exists, because
#: "looks like a long random string" matches every minified bundle on earth.
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI API key", re.compile(r"\bsk-[A-Za-z0-9]{32,}")),
    ("AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[0-9A-Za-z\-]{10,}")),
    ("Stripe secret key", re.compile(r"\b[sr]k_live_[0-9A-Za-z]{20,}")),
    ("Telegram bot token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{35}\b")),
    ("private key", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("credential in a URL", re.compile(r"://[^\s/:@]+:[^\s/@]{6,}@[^\s/]+")),
)

#: An assignment to a secret-ish name with a non-placeholder literal.
ASSIGNMENT = re.compile(
    r"""(?ix)
    \b(?:api[_-]?key|secret|token|passwd|password|private[_-]?key|access[_-]?key)
    \s*[:=]\s*
    ["'`]([^"'`\n]{8,})["'`]
    """
)

#: Things that are obviously not real. Keeps examples and docs usable.
#: `{name}` covers f-string and template interpolation — a hole where a value
#: goes is not a value.
PLACEHOLDER = re.compile(
    r"(?i)^(?:x{3,}|\.{3,}|<[^>]+>|\$?\{[^}]*\}|\$[a-z_]+|your[_-]|example|dummy"
    r"|placeholder|changeme|redacted|fake|test[_-]?(?:key|token)|abc123|null|none"
    r"|true|false)"
)

#: An escape hatch for fixtures and documentation that legitimately contain a
#: credential *shape*. Every use is reported as a warning rather than silently
#: honoured: a suppression an agent can add invisibly is a suppression an agent
#: will add invisibly. It shows up in the diff, in the gate output, and in the PR.
ALLOW = re.compile(r"(?i)#\s*longhaul:\s*allow-secret\b|//\s*longhaul:\s*allow-secret\b")

#: A committed .env is a leak waiting to happen even when today's copy is empty.
ENV_FILE = re.compile(r"(^|/)\.env(\.|$)")
ENV_ALLOWED = re.compile(r"(^|/)\.env\.(example|sample|template|dist)$")


def _looks_real(value: str) -> bool:
    return not PLACEHOLDER.match(value.strip())


class SecretsGate:
    name = "secrets"

    def check(self, diff: str) -> GateResult:
        from .cheat import _hunks

        result = GateResult(gate=self.name)
        files = _hunks(diff)
        result.checked = len(files)

        for path, _is_new, lines in files:
            if path == "/dev/null":
                continue

            if ENV_FILE.search(path) and not ENV_ALLOWED.search(path):
                result.findings.append(
                    Finding(
                        self.name,
                        "block",
                        "a .env file must never be committed — add it to .gitignore",
                        path,
                    )
                )

            for text, lineno in lines:
                if ALLOW.search(text):
                    result.findings.append(
                        Finding(
                            self.name,
                            "warn",
                            "secret check suppressed on this line — confirm it is a fixture",
                            path,
                            lineno,
                        )
                    )
                    continue
                for label, pattern in PATTERNS:
                    if pattern.search(text):
                        result.findings.append(
                            Finding(self.name, "block", f"{label} in the diff", path, lineno)
                        )
                        break
                else:
                    match = ASSIGNMENT.search(text)
                    if match and _looks_real(match.group(1)):
                        result.findings.append(
                            Finding(
                                self.name,
                                "block",
                                "a secret-looking assignment with a real-looking value",
                                path,
                                lineno,
                            )
                        )
        return result
