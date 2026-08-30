"""Does it actually run?

The distinction this file exists to hold: a proof step that *could not run* is
reported separately from one that ran and failed, and neither is a pass.
"""


import pytest

from longhaul.gates import proof

TOUCH = {
    "artifacts": {"apk": "build/app.apk"},
    "proof": {
        "kind": "screenshot",
        "steps": ["mkdir -p {proof_dir}", "echo shot > {proof_dir}/screenshot.png"],
    },
}


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "work").mkdir()
    return tmp_path / "work"


def run(profile, tree, tmp_path, **kw):
    return proof.run(profile, tree, tmp_path / "proof", **kw)


# --- the honest middle state ----------------------------------------------

def test_no_proof_declared_is_neither_pass_nor_fail(tree, tmp_path):
    r = run({}, tree, tmp_path)
    assert not r.ran and not r.ok and not r.passed
    assert "declares no proof" in r.detail


def test_a_missing_tool_is_reported_as_could_not_run(tree, tmp_path):
    """A machine without an emulator has demonstrated nothing either way."""
    profile = {"proof": {"kind": "emulator", "steps": ["definitely-not-a-real-binary --go"]}}
    r = run(profile, tree, tmp_path)
    assert not r.ran, "it must not claim to have run"
    assert not r.passed
    assert "missing on this machine" in r.detail
    assert "definitely-not-a-real-binary" in r.detail


def test_a_declared_kind_with_no_steps_is_not_a_pass(tree, tmp_path):
    r = run({"proof": {"kind": "screenshot"}}, tree, tmp_path)
    assert not r.ran and "no steps" in r.detail


# --- running it -----------------------------------------------------------

def test_a_successful_proof_captures_its_artefact(tree, tmp_path):
    r = run(TOUCH, tree, tmp_path)
    assert r.ran and r.ok and r.passed
    assert [p.name for p in r.artifacts] == ["screenshot.png"]
    assert r.steps_run == 2


def test_a_failing_step_stops_and_says_which(tree, tmp_path):
    profile = {"proof": {"kind": "x", "steps": ["true", "false", "echo never"]}}
    r = run(profile, tree, tmp_path)
    assert r.ran and not r.ok and not r.passed
    assert r.steps_run == 2, "it must stop at the failure, not keep going"
    assert "step 2 failed" in r.detail


def test_steps_that_exit_zero_but_produce_nothing_are_not_a_pass(tree, tmp_path):
    """The whole point: a green exit code that demonstrates nothing."""
    r = run({"proof": {"kind": "x", "steps": ["true"]}}, tree, tmp_path)
    assert r.ran and not r.ok
    assert "produced no artefact" in r.detail


def test_a_hanging_step_times_out_rather_than_blocking_forever(tree, tmp_path):
    """`adb wait-for-device` with nothing attached blocks indefinitely, and it
    hung this project's whole test suite the first time proof was wired in."""
    profile = {"proof": {"kind": "x", "steps": ["sleep 30"], "timeout_s": 1}}
    r = run(profile, tree, tmp_path)
    assert r.ran and not r.ok
    assert "timed out" in r.log


def test_a_profile_can_raise_the_timeout(tree, tmp_path):
    profile = {"proof": {"kind": "x", "steps": ["true"], "timeout_s": 5}}
    assert run(profile, tree, tmp_path).ran


# --- placeholders ---------------------------------------------------------

def test_placeholders_are_substituted(tree, tmp_path):
    profile = {
        "artifacts": {"apk": "build/app.apk"},
        "proof": {"kind": "x", "steps": [
            "mkdir -p {proof_dir}",
            "echo '{package} {artifacts.apk}' > {proof_dir}/out.txt",
        ]},
    }
    r = run(profile, tree, tmp_path, package="com.cybiqon.neondrift")
    assert r.passed
    written = (tmp_path / "proof" / "out.txt").read_text()
    assert "com.cybiqon.neondrift" in written
    assert "build/app.apk" in written


def test_an_unknown_placeholder_is_left_visible_not_blanked(tree, tmp_path):
    """Silently substituting an empty string turns a typo into a mystery."""
    profile = {"proof": {"kind": "x", "steps": [
        "mkdir -p {proof_dir}", "echo '{nonsense}' > {proof_dir}/out.txt"]}}
    r = run(profile, tree, tmp_path)
    assert r.passed
    assert "{nonsense}" in (tmp_path / "proof" / "out.txt").read_text()


# --- the shipped profile --------------------------------------------------

def test_the_flutter_profile_declares_a_real_proof_step():
    from longhaul import profiles

    spec = profiles.load("flutter-android")["proof"]
    assert spec["kind"] == "emulator_screenshot"
    assert any("screencap" in s for s in spec["steps"]), (
        "proof for a game has to be a picture of it running"
    )


def test_missing_tools_names_what_is_absent():
    profile = {"proof": {"steps": ["nope-not-here --x", "echo fine", "sleep 1"]}}
    assert proof.missing_tools(profile) == ["nope-not-here"]


def test_summary_distinguishes_could_not_run_from_failed(tree, tmp_path):
    could_not = run({"proof": {"kind": "e", "steps": ["nope-not-here"]}}, tree, tmp_path)
    failed = run({"proof": {"kind": "e", "steps": ["false"]}}, tree, tmp_path)
    assert "could not run" in could_not.summary()
    assert "FAILED" in failed.summary()
    assert could_not.summary() != failed.summary()


def test_the_flutter_profile_does_not_use_a_blocking_primitive():
    """`adb wait-for-device` blocks forever when nothing is attached — the wrong
    thing in a gate. It hung this project's whole test suite once already."""
    from longhaul import profiles

    spec = profiles.load("flutter-android")["proof"]
    everything = list(spec.get("requires") or []) + list(spec["steps"])
    assert not any("wait-for-device" in s for s in everything)
    assert any("get-state" in s for s in everything), "it still has to check for a device"


def test_every_shipped_profile_bounds_its_proof():
    from longhaul import profiles

    for name in profiles.available():
        spec = profiles.load(name).get("proof") or {}
        if spec.get("steps"):
            assert spec.get("timeout_s"), f"{name} does not bound its proof steps"


def test_a_failed_precondition_is_could_not_run_not_failed(tree, tmp_path):
    """An installed adb with no device attached means this machine cannot
    demonstrate anything. Failing the task there would burn a retry budget on
    every developer machine without an emulator running."""
    profile = {"proof": {"kind": "e", "requires": ["false"], "steps": ["true"]}}
    r = run(profile, tree, tmp_path)
    assert not r.ran, "a precondition failure must not read as a failed day"
    assert not r.passed
    assert "precondition not met" in r.detail
    assert "could not run" in r.summary()


def test_a_met_precondition_lets_the_steps_run(tree, tmp_path):
    profile = {"proof": {"kind": "e", "requires": ["true"], "steps": [
        "mkdir -p {proof_dir}", "echo x > {proof_dir}/shot.png"]}}
    assert run(profile, tree, tmp_path).passed


def test_a_step_failure_after_a_met_precondition_is_still_a_failure(tree, tmp_path):
    profile = {"proof": {"kind": "e", "requires": ["true"], "steps": ["false"]}}
    r = run(profile, tree, tmp_path)
    assert r.ran and not r.ok, "the environment was fine; the change was not"


def test_the_flutter_profile_treats_a_missing_device_as_a_precondition():
    from longhaul import profiles

    spec = profiles.load("flutter-android")["proof"]
    assert any("get-state" in c for c in spec["requires"])
    assert not any("get-state" in s for s in spec["steps"])
