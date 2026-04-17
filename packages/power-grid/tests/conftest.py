import pytest

from movici_simulation_core.core.moment import TimelineInfo


@pytest.fixture
def global_timeline_info():
    return TimelineInfo(0, 1, 0)


def get_dataset(name, ds_type, data, **kwargs):
    ds = {
        "version": 3,
        "name": name,
        "type": ds_type,
        "display_name": "",
        "epsg_code": 28992,
        "data": data,
    }
    ds.update(kwargs)
    return ds
