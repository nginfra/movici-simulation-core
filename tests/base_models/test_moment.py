import operator
from datetime import datetime

import pytest

from movici_simulation_core.core.moment import (
    Moment,
    TimelineInfo,
    get_timeline_info,
    set_timeline_info,
    string_to_datetime,
)


@pytest.fixture
def timeline_info():
    return TimelineInfo(reference=10, time_scale=2.0, start_time=0)


@pytest.fixture
def global_timeline_info(timeline_info):
    return timeline_info


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
        (str(int(datetime(2020, 1, 1).timestamp())), 0),
        ("01-01-2020", 0),
        ("02-01-2020", 86400),
    ],
)
def test_from_string(datetimestring, expected):
    reference = datetime(2020, 1, 1).timestamp()
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
def test_can_set_global_timeline_info(args, expected_seconds):
    if not isinstance(args, tuple):
        args = (args,)
    with set_timeline_info(*args):
        assert Moment(1) == expected_seconds


@pytest.mark.no_global_timeline_info
def test_can_temporarily_set_timeline_info():
    assert get_timeline_info() is None
    with set_timeline_info(TimelineInfo(0, 1, 0)):
        assert get_timeline_info() is not None
    assert get_timeline_info() is None


@pytest.mark.no_global_timeline_info
def test_raises_when_no_timeline_info():
    with pytest.raises(ValueError):
        Moment(1).seconds  # noqa: B018


@pytest.mark.parametrize(
    "input_str, kwargs, expected",
    [
        ("2021-02-01", {}, datetime(year=2021, month=2, day=1)),
        ("2021", {}, datetime(year=2021, month=1, day=1)),
        ("5000", {}, datetime(year=5000, month=1, day=1)),
        ("5001", {}, datetime.fromtimestamp(5001)),
        ("2001", {"max_year": 2000}, datetime.fromtimestamp(2001)),
        ("01-02-2021", {}, datetime(year=2021, month=1, day=2)),
        ("01-02-2021", {"dayfirst": False}, datetime(year=2021, month=1, day=2)),
        ("01-02-2021", {"dayfirst": True}, datetime(year=2021, month=2, day=1)),
        ("02021", {}, datetime(year=2021, month=1, day=1)),
    ],
)
def test_string_to_date_time(input_str, kwargs, expected):
    assert string_to_datetime(input_str, **kwargs) == expected
