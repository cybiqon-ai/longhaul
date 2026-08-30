"""Which projects exist on this machine.

A convenience index, never a source of truth: every project's own `.longhaul/`
is authoritative, and this only says where to look.
"""

import json

import pytest

from longhaul.core import registry


@pytest.fixture
def home(isolate_longhaul_home):
    """The suite-wide isolation, named for the tests that assert against it."""
    return isolate_longhaul_home


def project(tmp_path, name):
    path = tmp_path / name
    (path / ".longhaul").mkdir(parents=True)
    return path


def test_nothing_registered_is_an_empty_registry():
    assert registry.load().projects == []


def test_registering_a_project_makes_it_findable(tmp_path):
    p = registry.register(project(tmp_path, "neon-drift"))
    assert p.id == "neon-drift"
    assert registry.load().get("neon-drift").path == (tmp_path / "neon-drift").resolve()


def test_registering_twice_is_idempotent(tmp_path):
    path = project(tmp_path, "neon-drift")
    registry.register(path)
    registry.register(path)
    assert len(registry.load().projects) == 1


def test_ids_are_url_safe(tmp_path):
    assert registry.register(project(tmp_path, "My Game 2.0!")).id == "my-game-2-0"


def test_two_projects_with_the_same_directory_name_get_distinct_ids(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first = registry.register(project(tmp_path / "a", "app"))
    second = registry.register(project(tmp_path / "b", "app"))
    assert first.id != second.id
    assert second.id == "b-app", "disambiguate with the parent, not a counter"


def test_a_project_whose_directory_is_gone_is_reported_not_dropped(tmp_path):
    path = project(tmp_path, "neon-drift")
    registry.register(path)
    (path / ".longhaul").rmdir()
    entry = registry.load().get("neon-drift")
    assert entry is not None, "a project that vanished is something to be told about"
    assert not entry.exists


def test_forgetting_removes_the_entry_only(tmp_path):
    path = project(tmp_path, "neon-drift")
    registry.register(path)
    assert registry.forget("neon-drift")
    assert registry.load().projects == []
    assert (path / ".longhaul").is_dir(), "the project itself must be untouched"


def test_forgetting_something_unknown_says_so():
    assert registry.forget("nope") is False


def test_a_corrupt_index_does_not_stop_the_tool(home):
    home.mkdir(parents=True, exist_ok=True)
    (home / "projects.json").write_text("{not json")
    assert registry.load().projects == []


def test_entries_missing_a_path_are_skipped(home):
    home.mkdir(parents=True, exist_ok=True)
    (home / "projects.json").write_text(json.dumps(
        {"projects": [{"id": "ok", "path": "/tmp/x"}, {"id": "broken"}]}))
    assert [p.id for p in registry.load().projects] == ["ok"]


def test_the_registry_lives_outside_any_repository(tmp_path, monkeypatch):
    """It is about this machine, not about any one project."""
    monkeypatch.setenv("LONGHAUL_HOME", str(tmp_path / "elsewhere"))
    import importlib

    importlib.reload(registry)
    assert tmp_path / "elsewhere" / "projects.json" == registry.REGISTRY_PATH
    importlib.reload(registry)


def test_init_registers_the_project(tmp_path):
    import subprocess

    from longhaul.core import init

    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    result = init.run(root, profile="flutter-android", target=root / "target.md")
    assert result.ok
    assert any("registered as project" in c for c in result.created)


def test_the_suite_cannot_reach_the_real_home(isolate_longhaul_home, tmp_path):
    """This exists because it once could: a suite run left 38 entries pointing
    at pytest temp directories in a developer's actual registry."""
    from pathlib import Path

    assert isolate_longhaul_home / "projects.json" == registry.REGISTRY_PATH
    assert Path.home() not in registry.REGISTRY_PATH.parents
    registry.register(project(tmp_path, "sandboxed"))
    assert registry.REGISTRY_PATH.is_file()
