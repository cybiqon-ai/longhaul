"""The proof gallery — every day's artefact, in one strip.

For an open-source project this is the most persuasive thing the tool produces:
fourteen screenshots of an application visibly appearing, one per day, each one
something a person can look at rather than a number they have to trust.

Images are embedded as data URIs so the page stays genuinely self-contained —
`report.html` has to open from a CI artefact or an email attachment with the
`.longhaul/` directory nowhere near it. Above a size cap they are linked
relatively instead, and the page says which, because a 40MB HTML file nobody can
open is not a better outcome than a link.
"""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}

#: Per image. A screenshot is typically well under this; a screen recording is
#: not, and embedding one would make the page unopenable.
MAX_EMBED_BYTES = 512 * 1024
#: Across the whole page, so a long project cannot quietly produce a 40MB file.
MAX_TOTAL_EMBED_BYTES = 6 * 1024 * 1024


@dataclass
class Artefact:
    path: Path
    day: int
    task_id: str
    is_image: bool = False
    data_uri: str | None = None
    href: str | None = None
    size: int = 0

    @property
    def embedded(self) -> bool:
        return self.data_uri is not None


@dataclass
class Gallery:
    artefacts: list[Artefact] = field(default_factory=list)
    embedded_bytes: int = 0
    linked: int = 0

    @property
    def images(self) -> list[Artefact]:
        return [a for a in self.artefacts if a.is_image]

    @property
    def others(self) -> list[Artefact]:
        return [a for a in self.artefacts if not a.is_image]


def _parse(path: Path, root: Path) -> tuple[int, str] | None:
    """`.longhaul/proof/day-07/t9/shot.png` → (7, "t9")."""
    try:
        rel = path.relative_to(root / ".longhaul" / "proof")
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 2 or not parts[0].startswith("day-"):
        return None
    try:
        return int(parts[0].removeprefix("day-")), parts[1]
    except ValueError:
        return None


def collect(root: Path, embed: bool = True) -> Gallery:
    gallery = Gallery()
    proof_dir = root / ".longhaul" / "proof"
    if not proof_dir.is_dir():
        return gallery

    for path in sorted(proof_dir.rglob("*")):
        if not path.is_file():
            continue
        parsed = _parse(path, root)
        if parsed is None:
            continue
        day, task_id = parsed

        artefact = Artefact(
            path=path, day=day, task_id=task_id,
            is_image=path.suffix.lower() in IMAGE_SUFFIXES,
            size=path.stat().st_size,
            href=str(path.relative_to(root)),
        )

        room = MAX_TOTAL_EMBED_BYTES - gallery.embedded_bytes
        if embed and artefact.is_image and artefact.size <= min(MAX_EMBED_BYTES, room):
            mime = mimetypes.guess_type(path.name)[0] or "image/png"
            encoded = base64.b64encode(path.read_bytes()).decode()
            artefact.data_uri = f"data:{mime};base64,{encoded}"
            gallery.embedded_bytes += artefact.size
        elif artefact.is_image:
            gallery.linked += 1

        gallery.artefacts.append(artefact)

    gallery.artefacts.sort(key=lambda a: (a.day, a.task_id, a.path.name))
    return gallery
