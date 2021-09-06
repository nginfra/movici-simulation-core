import operator
import datetime

import pytest

from movici_simulation_core.base_models.moment import (
    TimelineInfo,
    set_timeline_info,
    get_timeline_info,
    Moment,
)


@pytest.fixture
def timeline_info():
    return TimelineInfo(reference=10, time_scale=2.0, start_time=0)


@pytest.fixture
def set_global_timeline_info():
    curr = get_timeline_info()

    def set_info(*args, **kwargs):
        set_timeline_info(*args, **kwargs)
        return get_timeline_info()

    yield set_info
    set_timeline_info(curr)


@pytest.fixture
def global_timeline_info(timeline_info, set_global_timeline_info):
    set_global_timeline_info(timeline_info)


def test_can_read_seconds(timeline_info):
    assert Moment(1, timeline_info=timeline_info).seconds == 2


def test_can_read_world_time(timeline_info):
    assert Moment(1, timeline_info=timeline_info).world_time == 12


@pytest.mark.parametrize(
    "a, b, op, expected",
    [
        (Moment(1), Moment(1), operator.eq, True),
        (Moment(1), Moment(2), operator.eq, False),
        (2, Moment(1), operator.eq, True),
        (Moment(1), 2, operator.eq, True),
        (Moment(1), Moment(2), operator.lt, True),
        (Moment(1), 3, operator.lt, True),
        (1, Moment(3), operator.lt, True),
        (Moment(1), Moment(2), operator.gt, False),
        (Moment(1, TimelineInfo(0, 2, 0)), Moment(2, TimelineInfo(0, 1, 0)), operator.eq, True),
    ],
)
def test_compare_moments(global_timeline_info, a, b, op, expected):
    assert op(a, b) == expected


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (2.0, 2.0),
        (3.1, 2.0),
        (3.9, 2.0),
        (4.0, 4.0),
    ],
)
def test_from_seconds(seconds, expected, timeline_info):
    assert Moment.from_seconds(seconds, timeline_info) == expected


@pytest.mark.parametrize(
    "datetimestring, expected",
    [
        ("2020", 0),
        ("1577833200", 0),
        ("01-01-2020", 0),
        ("02-01-2020", 86400),
    ],
)
def test_from_string(datetimestring, expected):
    reference = datetime.datetime(2020, 1, 1).timestamp()
    timeline_info = TimelineInfo(reference=reference, time_scale=1, start_time=0)
    assert Moment.from_string(datetimestring, timeline_info) == Moment(
        expected, timeline_info=timeline_info
    )


@pytest.mark.parametrize(
    "args, expected_seconds",
    [
        (TimelineInfo(0, 10, 0), 10.0),
        ((0, 10, 0), 10.0),
    ],
)
def test_can_set_global_timeline_info(args, expected_seconds, set_global_timeline_info):
    if not isinstance(args, tuple):
        args = (args,)
    set_global_timeline_info(*args)
    assert Moment(1) == expected_seconds


def test_raises_when_no_timeline_info():
    with pytest.raises(ValueError):
        Moment(1).seconds
