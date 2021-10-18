import pytest

from movici_simulation_core.utils.moment import set_timeline_info


def pytest_configure(config):
    config.addinivalue_line("markers", "no_global_timeline_info")


@pytest.fixture
def global_timeline_info():
    return None


@pytest.fixture(autouse=True)
def set_global_timeline_info(global_timeline_info, request):
    if "no_global_timeline_info" in request.keywords:
        yield
    else:
        with set_timeline_info(global_timeline_info):
            yield
