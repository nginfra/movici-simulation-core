from contextlib import nullcontext as does_not_raise

import numpy as np
import pandas as pd
import pytest

from movici_simulation_core.core.moment import Moment, TimelineInfo
from movici_simulation_core.models.common.csv_tape import CsvTape


@pytest.fixture
def csv_df():
    seconds = [0, 1, 5, 10]
    a = [1.0, 1.01, 1.05, 1.1]
    b = [2.0, 2.01, 2.05, 2.10]
    return pd.DataFrame({"seconds": seconds, "a": a, "b": b})


@pytest.fixture
def csv_tape(csv_df):
    tape = CsvTape()
    tape.initialize(csv_df)
    return tape


@pytest.mark.parametrize(
    "timeline_info, expected",
    [
        (TimelineInfo(0, time_scale=1), [0, 1, 5, 10]),
        (TimelineInfo(0, time_scale=0.5), [0, 2, 10, 20]),
        (None, [0, 1, 5, 10]),
    ],
)
def test_initialize_sets_up_timeline(csv_df, timeline_info, expected):
    tape = CsvTape(timeline_info)
    tape.initialize(csv_df)
    assert np.array_equal(tape.timeline, expected)


@pytest.mark.parametrize(
    "moment, key, expected",
    [
        (Moment(0), "a", 1.0),
        (Moment(0), "b", 2.0),
        (Moment(1), "a", 1.01),
        (Moment(2), "a", 1.01),
        (Moment(5), "a", 1.05),
        (Moment(5), "a", 1.05),
    ],
)
def test_can_lookup_values(csv_tape, moment, key, expected):
    csv_tape.proceed_to(moment)
    assert csv_tape[key] == expected


@pytest.mark.parametrize(
    "current_time, expected",
    [
        (Moment(0), Moment(1)),
        (Moment(1), Moment(5)),
        (Moment(2), Moment(5)),
        (Moment(10), None),
    ],
)
def test_get_next_timestamp(csv_tape, current_time, expected):
    csv_tape.proceed_to(current_time)
    assert csv_tape.get_next_timestamp() == expected


@pytest.mark.parametrize(
    "parameter, expectation",
    [
        ("a", does_not_raise()),
        ("invalid", pytest.raises(RuntimeError)),
    ],
)
def test_ensure_parameter(csv_tape, parameter, expectation):
    with expectation:
        csv_tape.assert_parameter(parameter)


def test_raises_on_nonsorted(csv_df):
    csv_df["seconds"] = [0, 1, 3, 2]
    tape = CsvTape()
    with pytest.raises(ValueError):
        tape.initialize(csv_df)
