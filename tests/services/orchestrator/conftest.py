import time
from unittest.mock import MagicMock, Mock

import pytest

from movici_simulation_core.services.orchestrator.context import Context, ModelCollection


class Clock:
    def __init__(self, start=0):
        self.now = start

    def step(self):
        self.now += 1

    def __call__(self):
        return self.now


@pytest.fixture(autouse=True)
def patch_time(monkeypatch):
    monkeypatch.setattr(time, "monotonic", Clock())


@pytest.fixture
def context():
    models = MagicMock(ModelCollection)
    return Context(models=models, timeline=Mock(), phase_timer=Mock(), global_timer=Mock())
