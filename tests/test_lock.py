"""A scheduled job that can overlap itself will, the first time a run takes
longer than its interval."""

import pytest

from longhaul.core.lock import AlreadyRunning, acquire


def test_a_second_acquire_is_refused(tmp_path):
    with acquire(tmp_path), pytest.raises(AlreadyRunning), acquire(tmp_path):
        pass


def test_the_lock_is_released_afterwards(tmp_path):
    with acquire(tmp_path):
        pass
    with acquire(tmp_path):
        pass  # no exception


def test_the_lock_file_records_the_pid_and_the_process_group(tmp_path):
    """Both, because the parent alone is not what needs killing."""
    import os

    from longhaul.core import lock

    with acquire(tmp_path):
        pid, pgid = lock.read(tmp_path)
    assert pid == os.getpid()
    assert pgid == os.getpgid(0)


def test_reading_a_missing_lock_is_not_an_error(tmp_path):
    from longhaul.core import lock

    assert lock.read(tmp_path) == (None, None)


def test_a_lock_from_an_older_version_with_only_a_pid_still_reads(tmp_path):
    from longhaul.core import lock

    path = tmp_path / ".longhaul" / "lock"
    path.parent.mkdir(parents=True)
    path.write_text("12345\n")
    assert lock.read(tmp_path) == (12345, None)


def test_an_empty_process_group_is_reported_as_dead():
    from longhaul.core import lock

    assert lock.group_is_alive(None) is False
    assert lock.group_is_alive(999_999) is False


def test_our_own_process_group_is_alive():
    import os

    from longhaul.core import lock

    assert lock.group_is_alive(os.getpgid(0)) is True
