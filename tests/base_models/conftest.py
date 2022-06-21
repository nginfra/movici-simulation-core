import pytest

from movici_simulation_core.core.moment import TimelineInfo
from movici_simulation_core.settings import Settings


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def global_timeline_info():
    return TimelineInfo(0, 1, 0)
