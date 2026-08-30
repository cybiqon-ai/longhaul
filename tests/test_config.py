from longhaul.schema.config import Config


def test_defaults_are_conservative():
    c = Config()
    assert c.auto_merge is False, "the single biggest trust decision stays off"
    assert c.push is True
    assert c.limits.max_attempts == 3
    assert c.limits.identical_failures == 2
    assert c.notify.backend == "none"


def test_missing_file_gives_defaults(tmp_path):
    assert Config.load(tmp_path).auto_merge is False


def test_partial_config_keeps_the_other_defaults(tmp_path):
    (tmp_path / ".longhaul").mkdir()
    (tmp_path / ".longhaul" / "config.yml").write_text(
        "profile: nextjs-web\nlimits:\n  cost_usd_per_day: 3.5\n"
    )
    c = Config.load(tmp_path)
    assert c.profile == "nextjs-web"
    assert c.limits.cost_usd_per_day == 3.5
    assert c.limits.max_attempts == 3
    assert c.auto_merge is False


def test_unknown_keys_are_ignored_rather_than_crashing(tmp_path):
    (tmp_path / ".longhaul").mkdir()
    (tmp_path / ".longhaul" / "config.yml").write_text(
        "profile: x\nfuture_option: 1\nlimits:\n  future_limit: 2\n"
    )
    assert Config.load(tmp_path).profile == "x"
