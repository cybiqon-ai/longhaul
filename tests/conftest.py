"""Suite-wide isolation.

`longhaul init` registers a project in `~/.longhaul/projects.json`, which means
any test touching init writes to the real home directory of whoever runs the
suite. It did: a run of this suite left 38 entries pointing at pytest temp
directories in a developer's actual registry.

A test must never be able to reach outside its tmp_path. This redirects the
registry for every test, whether or not the test knows the registry exists.
"""

from __future__ import annotations

import pytest

from longhaul.core import registry


@pytest.fixture(autouse=True)
def isolate_longhaul_home(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp("longhaul-home")
    monkeypatch.setenv("LONGHAUL_HOME", str(home))
    monkeypatch.setattr(registry, "REGISTRY_DIR", home)
    monkeypatch.setattr(registry, "REGISTRY_PATH", home / "projects.json")
    return home
