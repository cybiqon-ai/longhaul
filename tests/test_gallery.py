"""The proof gallery — every day's artefact in one strip.

For an open-source project this is the most persuasive thing the tool produces:
fourteen screenshots of an application visibly appearing, one per day.
"""

import base64

import pytest

from longhaul.ui import gallery


def put(root, day, task_id, name, data=b"\x89PNG\r\n"):
    path = root / ".longhaul" / "proof" / f"day-{day:02d}" / task_id / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_nothing_to_show_is_an_empty_gallery(tmp_path):
    g = gallery.collect(tmp_path)
    assert g.artefacts == [] and g.images == []


def test_it_finds_artefacts_and_reads_the_day_and_task_from_the_path(tmp_path):
    put(tmp_path, 1, "t1", "screenshot.png")
    put(tmp_path, 7, "t9", "screenshot.png")
    g = gallery.collect(tmp_path)
    assert [(a.day, a.task_id) for a in g.images] == [(1, "t1"), (7, "t9")]


def test_it_sorts_by_day_so_the_strip_reads_as_a_sequence(tmp_path):
    for day in (11, 2, 7):
        put(tmp_path, day, "t1", "screenshot.png")
    assert [a.day for a in gallery.collect(tmp_path).images] == [2, 7, 11]


def test_images_are_embedded_so_the_page_stays_self_contained(tmp_path):
    """report.html has to open from a CI artefact with .longhaul/ nowhere near."""
    put(tmp_path, 1, "t1", "screenshot.png", b"\x89PNG\r\nrealbytes")
    shot = gallery.collect(tmp_path).images[0]
    assert shot.embedded
    assert shot.data_uri.startswith("data:image/png;base64,")
    assert base64.b64decode(shot.data_uri.split(",", 1)[1]) == b"\x89PNG\r\nrealbytes"


def test_a_large_image_is_linked_rather_than_embedded(tmp_path):
    """A 40MB HTML file nobody can open is not better than a link."""
    put(tmp_path, 1, "t1", "big.png", b"x" * (gallery.MAX_EMBED_BYTES + 1))
    g = gallery.collect(tmp_path)
    assert not g.images[0].embedded
    assert g.linked == 1
    assert g.images[0].href.startswith(".longhaul/proof/")


def test_the_total_embed_budget_is_respected(tmp_path, monkeypatch):
    monkeypatch.setattr(gallery, "MAX_TOTAL_EMBED_BYTES", 1000)
    for day in range(1, 6):
        put(tmp_path, day, "t1", "shot.png", b"x" * 400)
    g = gallery.collect(tmp_path)
    assert g.embedded_bytes <= 1000
    assert g.linked >= 1, "the rest must be linked, not dropped"
    assert len(g.images) == 5, "nothing is silently discarded"


def test_non_images_are_listed_separately_not_embedded(tmp_path):
    put(tmp_path, 1, "t1", "app.apk", b"PK\x03\x04")
    put(tmp_path, 1, "t1", "build.log", b"ok")
    g = gallery.collect(tmp_path)
    assert {a.path.name for a in g.others} == {"app.apk", "build.log"}
    assert g.images == []


def test_embedding_can_be_turned_off_for_the_live_server(tmp_path):
    """Served locally the browser can fetch them, so the page stays small
    however long the project runs."""
    put(tmp_path, 1, "t1", "screenshot.png")
    g = gallery.collect(tmp_path, embed=False)
    assert not g.images[0].embedded
    assert g.embedded_bytes == 0


def test_files_outside_the_day_layout_are_ignored(tmp_path):
    stray = tmp_path / ".longhaul" / "proof" / "notes.txt"
    stray.parent.mkdir(parents=True)
    stray.write_text("x")
    assert gallery.collect(tmp_path).artefacts == []


@pytest.mark.parametrize("suffix", [".png", ".jpg", ".webp", ".gif"])
def test_common_image_types_are_recognised(tmp_path, suffix):
    put(tmp_path, 1, "t1", f"shot{suffix}")
    assert gallery.collect(tmp_path).images


def test_the_gallery_reaches_the_page(tmp_path):
    import yaml

    from longhaul.schema.plan import Plan
    from longhaul.schema.state import State
    from longhaul.ui import render

    put(tmp_path, 3, "t5", "screenshot.png")
    plan = Plan.from_dict(yaml.safe_load("""
project: Neon Drift
target_days: 3
profile: flutter-android
milestones:
- id: m1
  title: Core
  tasks:
  - {id: t5, day: 3, title: Engine, acceptance_criteria: [a]}
"""))
    out = tmp_path / "report.html"
    render.write(plan, State(), out, root=tmp_path)
    page = out.read_text()
    assert "<h2>Proof</h2>" in page
    assert "day 3 · t5" in page
    assert "data:image/png;base64," in page
