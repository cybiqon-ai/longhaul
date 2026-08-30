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


def test_the_lock_file_records_the_pid(tmp_path):
    import os

    with acquire(tmp_path) as path:
        assert path.read_text().strip() == str(os.getpid())
