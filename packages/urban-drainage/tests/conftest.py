import pytest

from movici_simulation_core.core.moment import TimelineInfo


@pytest.fixture
def global_timeline_info():
    return TimelineInfo(0, 1, 0)
