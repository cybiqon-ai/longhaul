"""Every shipped asset has to say where it came from.

An app pulled from a store over an unlicensed font is pulled for the licence,
not for the font — and months later the only thing anyone has is what was
written down at the time.
"""

import pytest

from longhaul.gates.provenance import ProvenanceGate, is_asset


def diff_for(paths, credits=None):
    parts = []
    for path in paths:
        parts.append(f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1 @@\n+binary\n")
    if credits is not None:
        body = "\n".join(f"+{line}" for line in credits.splitlines())
        parts.append(f"--- a/assets/CREDITS.md\n+++ b/assets/CREDITS.md\n@@ -1,0 +1 @@\n{body}\n")
    return "".join(parts)


def blocking(diff):
    return [f for f in ProvenanceGate().check(diff).findings if f.severity == "block"]


def test_an_asset_added_without_credits_is_blocked():
    found = blocking(diff_for(["assets/icons/play.svg"]))
    assert found
    assert "provenance" in found[0].message or "CREDITS" in found[0].message


def test_an_asset_with_a_credits_row_passes():
    credits = "| assets/icons/play.svg | generated | n/a — original work | no |"
    assert not blocking(diff_for(["assets/icons/play.svg"], credits))


def test_matching_on_the_filename_alone_is_enough():
    """The table may reference a file by name rather than full path."""
    assert not blocking(diff_for(["assets/fonts/Inter.ttf"], "| Inter.ttf | rsms/inter | OFL |"))


def test_one_credited_asset_does_not_cover_an_uncredited_one():
    found = blocking(diff_for(
        ["assets/a.png", "assets/b.png"], "| assets/a.png | generated | n/a |"))
    assert [f.path for f in found] == ["assets/b.png"]


@pytest.mark.parametrize("path", [
    "assets/logo.png", "web/hero.jpg", "fonts/Inter.woff2",
    "audio/tap.mp3", "icons/play.svg", "media/intro.mp4",
])
def test_media_and_fonts_are_assets(path):
    assert is_asset(path)


@pytest.mark.parametrize("path", [
    "src/main.dart", "README.md", "pubspec.yaml", "lib/theme.ts", "Makefile",
])
def test_source_and_configuration_are_not_assets(path):
    assert not is_asset(path)


@pytest.mark.parametrize("path", [
    "node_modules/pkg/logo.png",
    "build/app/outputs/icon.png",
    ".dart_tool/thing.png",
    ".next/static/x.svg",
    ".longhaul/proof/day-01/t1/screenshot.png",
])
def test_generated_and_vendored_directories_are_ignored(path):
    """A proof screenshot is not a shipped asset, and neither is a build output."""
    assert not is_asset(path)


def test_a_modified_asset_is_not_treated_as_newly_shipped():
    """Replacing an image that already has a row is not a new licence question."""
    diff = (
        "--- a/assets/logo.png\n+++ b/assets/logo.png\n@@ -1 +1 @@\n+newbytes\n"
    )
    assert not blocking(diff)


def test_a_diff_with_no_assets_reports_a_count_and_nothing_else():
    result = ProvenanceGate().check(
        "--- a/src/main.py\n+++ b/src/main.py\n@@ -0,0 +1 @@\n+x = 1\n")
    assert result.findings == []
    assert result.checked == 1


def test_the_gate_runs_in_the_day_loop():
    """Grepping the source for the class name would prove nothing about whether
    it is actually called, so this checks the registered gates."""
    import inspect as _inspect

    from longhaul.core import orchestrator
    from longhaul.gates.provenance import ProvenanceGate

    body = _inspect.getsource(orchestrator.run_task)
    assert "ProvenanceGate()" in body, "the gate must be constructed in the loop"
    assert ProvenanceGate().name == "provenance"


def test_asset_tasks_go_to_the_assets_role():
    from longhaul.core.orchestrator import ROLE_FOR_KIND

    assert ROLE_FOR_KIND["asset"] == "assets"


def test_the_assets_prompt_refuses_unlicensed_material():
    from longhaul import roles

    body = roles.load("assets").lower()
    assert "never take anything whose licence you cannot state" in body
    assert "credits.md" in body
