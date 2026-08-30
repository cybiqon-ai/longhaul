"""Every shipped asset has to say where it came from.

An application pulled from a store over an unlicensed font is pulled for the
licence, not for the font. Months later the only thing anyone has is what was
written down at the time — so an asset added without a `CREDITS.md` row is
blocked here rather than discovered by a store review.

Deterministic, like every gate: it reads the diff, not the intent.
"""

from __future__ import annotations

import re

from .base import Finding, GateResult

#: Binary and media files a licence question can attach to. Source files and
#: configuration are not assets, whatever directory they sit in.
ASSET_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".svg", ".ico",
    ".ttf", ".otf", ".woff", ".woff2",
    ".mp3", ".wav", ".ogg", ".m4a", ".flac",
    ".mp4", ".webm", ".mov",
}

#: Where a credits table is looked for. The first that exists in the diff wins.
CREDITS_NAMES = ("assets/CREDITS.md", "CREDITS.md", "docs/CREDITS.md", "ATTRIBUTION.md")

#: Directories whose contents are generated or vendored, not authored here.
IGNORED = re.compile(
    r"(^|/)(node_modules|build|dist|\.dart_tool|\.next|vendor|third_party|"
    r"\.longhaul|__pycache__)/"
)


def is_asset(path: str) -> bool:
    if IGNORED.search(path):
        return False
    return any(path.lower().endswith(suffix) for suffix in ASSET_SUFFIXES)


class ProvenanceGate:
    name = "provenance"

    def check(self, diff: str) -> GateResult:
        from .cheat import _hunks

        result = GateResult(gate=self.name)
        files = _hunks(diff)
        result.checked = len(files)

        added_assets = [path for path, is_new, _lines in files if is_new and is_asset(path)]
        if not added_assets:
            return result

        # The credits table as it stands *after* this change: added lines from a
        # credits file in this diff, plus whatever the diff shows as context.
        credited = "\n".join(
            "\n".join(text for text, _ in lines)
            for path, _is_new, lines in files
            if any(path.endswith(name) for name in CREDITS_NAMES)
        )

        for path in added_assets:
            name = path.rsplit("/", 1)[-1]
            if path in credited or name in credited:
                continue
            result.findings.append(
                Finding(
                    self.name,
                    "block",
                    "shipped without provenance — add a row to assets/CREDITS.md "
                    "naming its origin and licence",
                    path,
                )
            )
        return result
