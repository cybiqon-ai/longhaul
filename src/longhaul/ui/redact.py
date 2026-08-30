"""Strip credentials out of anything on its way to a browser.

The report and the live server both render agent output verbatim — a build log,
a stack trace, an error from a git remote. Any of those can contain a token, and
`report.html` is a file people commit, attach to issues and screenshot.

This reuses the secrets gate's patterns rather than inventing a second list, so
a pattern added for the gate protects the UI too.
"""

from __future__ import annotations

import re

from ..gates.secrets import PATTERNS

MASK = "***redacted***"

#: `user:token@host` in a URL. The host is kept — an error naming the remote is
#: useful, an error naming the credential is a leak.
CREDENTIAL_IN_URL = re.compile(r"(://)[^\s/:@]+:[^\s/@]+@")


def redact(text: str | None) -> str:
    if not text:
        return ""
    out = CREDENTIAL_IN_URL.sub(r"\1***:***@", text)
    for _label, pattern in PATTERNS:
        out = pattern.sub(MASK, out)
    return out
