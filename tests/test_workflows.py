"""Every workflow file must parse.

A workflow whose YAML is invalid does not fail a job — it fails the whole run
before any job starts, with zero jobs and no logs to read. That is the exact
shape of failure this project is about: something reports a status while having
checked nothing. It happened on this repository's first push, to this file, and
the cause was a `: ` inside a plain YAML scalar.
"""

from pathlib import Path

import pytest
import yaml

WORKFLOWS = sorted(Path(__file__).resolve().parents[1].glob(".github/workflows/*.yml"))


def test_there_is_at_least_one_workflow():
    assert WORKFLOWS, "no workflows found — this test would otherwise check nothing"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_parses(path):
    spec = yaml.safe_load(path.read_text())
    assert isinstance(spec, dict)
    # `on:` is parsed by YAML 1.1 as the boolean True, which is expected.
    assert "jobs" in spec and spec["jobs"], f"{path.name} defines no jobs"
    assert True in spec or "on" in spec, f"{path.name} has no trigger"
