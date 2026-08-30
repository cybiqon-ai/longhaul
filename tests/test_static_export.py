"""The bundled interface.

These check the *built* export rather than the source, because the failure this
file exists to catch was invisible in the source: every component looked right,
the build succeeded, and the page rendered completely unstyled.

Tailwind 4 dropped the v3 `bg-[--color-panel]` arbitrary-value syntax. It does
not error on it — it silently generates nothing. So the HTML referenced classes
that the stylesheet did not define, and nothing anywhere reported a problem.
"""

import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "src" / "longhaul" / "ui" / "static"

pytestmark = pytest.mark.skipif(
    not STATIC.is_dir(),
    reason="no export bundled — run `cd web && npm run build`",
)


def css_text() -> str:
    return "".join(p.read_text(encoding="utf-8") for p in STATIC.rglob("*.css"))


def html_text() -> str:
    return "".join(p.read_text(encoding="utf-8") for p in STATIC.rglob("*.html"))


def test_the_export_has_html_and_css():
    assert list(STATIC.rglob("*.html")), "no pages were exported"
    assert list(STATIC.rglob("*.css")), "no stylesheet was emitted"


def test_the_pages_link_the_stylesheet():
    assert re.search(r'href="[^"]+\.css"', html_text())


def test_every_theme_colour_utility_the_markup_uses_is_defined():
    """The bug in full: HTML referencing classes the CSS never defined."""
    css = css_text()
    used = set(
        re.findall(
            r"\b(?:bg|text|border|divide|ring|fill|stroke)-"
            r"(?:surface|panel|panel-2|line|line-2|ink|ink-2|muted|accent|accent-soft"
            r"|done|failed|parked|halted|running|pending)\b",
            html_text(),
        )
    )
    assert used, "the markup uses no theme colours at all, which cannot be right"
    missing = sorted(u for u in used if f".{u}{{" not in css and f".{u}:" not in css)
    assert not missing, f"classes used but never generated: {missing}"


def test_no_tailwind_v3_arbitrary_colour_syntax_survives():
    """`bg-[--color-x]` generates nothing in Tailwind 4, silently."""
    offenders = [p.name for p in STATIC.rglob("*.html") if "-[--color-" in p.read_text()]
    assert not offenders, f"v3 syntax left in: {offenders}"


def test_the_theme_variables_are_defined_and_overridden_for_dark():
    css = css_text()
    assert "--color-panel:" in css
    assert ".dark" in css, "the dark theme override must survive the build"


def test_the_project_route_is_prerendered_under_its_placeholder():
    """The server rewrites /p/<id>/tasks onto these, so they have to exist."""
    for name in ("_.html", "_/tasks.html", "_/runs.html", "_/chats.html"):
        assert (STATIC / "p" / name).is_file(), f"missing export: p/{name}"


def test_the_projects_page_is_not_squeezed_into_a_sidebar_column():
    """The Projects screen has no sidebar.

    The shell applied `md:grid-cols-[232px_1fr]` unconditionally, so with a
    single child the whole page landed in the *first* column and rendered 232px
    wide. Everything looked styled and was simply unreadable — which no CSS
    check catches, because the classes were all correctly generated.
    """
    home = (STATIC / "index.html").read_text()
    assert "grid min-h-screen" in home
    assert "md:grid-cols-[232px_1fr]" not in home, (
        "the projects page must not reserve a sidebar column it has no sidebar for"
    )


def test_a_project_page_does_keep_its_sidebar_column():
    project = (STATIC / "p" / "_.html").read_text()
    assert "md:grid-cols-[232px_1fr]" in project
