import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config  # noqa: E402


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def cfg(tmp_path):
    c = Config(str(tmp_path / "config.json"), data={
        "api_key": "sk-test", "model": "test-model",
        "workspaces_dir": str(tmp_path / "ws"), "data_dir": str(tmp_path / "data"),
        "archive_dir": str(tmp_path / "archive"),
        "allowed_dirs": [str(tmp_path / "ws")], "sandbox": "none",
        "verify_on_finish": False, "endless_mode": False,
        "max_retries": 4, "retry_delays": [10, 20, 40, 60],
        "retry_jitter": 0, "retry_overloaded_forever": False, "spec_docs": False,
    })
    c.save()
    return c


@pytest.fixture
def sleeps():
    return []
