import typing as t

import numpy as np
import pytest
from movici_simulation_core.data_tracker.property import UniformProperty, DataType, PUB
from movici_simulation_core.models.area_aggregation.aggregators import (
    PropertyAggregator,
    func_avg,
    func_sum,
    func_integral,
    func_integral_minutes,
    func_integral_hours,
    func_integral_days,
    func_min,
    func_max,
)
from boost_geo_query.geo_query import QueryResult


@pytest.fixture
def int_data():
    def get(data: t.List[int]):
        data_type = DataType(int, (), False)
        return UniformProperty(data=data, data_type=data_type, flags=PUB)

    return get


@pytest.fixture
def float_data():
    def get(data: t.List[float]):
        data_type = DataType(float, (), False)
        return UniformProperty(data=data, data_type=data_type, flags=PUB)

    return get


@pytest.mark.parametrize(
    ["func", "result"], [(func_max, 7), (func_min, 1), (func_avg, 4), (func_sum, 12)]
)
def test_aggregator_functions(int_data, func, result):
    source = int_data([1, 4, 7])
    assert func(source=source.array, special=-1, weights=np.ones(len(source))) == result


@pytest.mark.parametrize(
    ["func", "result", "dt", "previous_target"],
    [
        (func_integral, 12, 1, 0),
        (func_integral, 17, 1, 5),
        (func_integral, 24, 2, 0),
        (func_integral_minutes, 12, 60, 0),
        (func_integral_hours, 12, 60 * 60, 0),
        (func_integral_days, 12, 60 * 60 * 24, 0),
    ],
)
def test_integral_aggregator_functions(int_data, func, result, dt, previous_target):
    source = int_data([1, 4, 7])
    assert np.array_equal(
        func(
            previous_source=source.array,
            dt=dt,
            previous_target=previous_target,
            special=-1,
            weights=np.ones(len(source)),
        ),
        result,
    )


@pytest.fixture
def aggregator(float_data):
    def get(func="max", previous_source=None):
        source = float_data([0, 5, 7])
        target = float_data([2, 0, 6])
        mapping = QueryResult(indices=np.array([0, 1, 0, 1, 2]), row_ptr=np.array([0, 2, 2, 5]))
        return PropertyAggregator(
            source=source,
            target=target,
            func=func,
            mapping=mapping,
            default_special_value=-1,
            previous_source=previous_source,
        )

    return get


def test_can_initialize_aggregator(aggregator):
    agg = aggregator("max")
    assert np.array_equal(agg.source.array, np.array([0, 5, 7]))
    assert np.array_equal(agg.target.array, np.array([2, 0, 6]))
    assert agg.function == func_max


@pytest.mark.parametrize(
    ["func", "result"],
    [
        ("max", [5, -1, 7]),
        ("min", [0, -1, 0]),
        ("average", [2.5, -1, 4]),
        ("sum", [5, 0, 12]),
    ],
)
def test_aggregate(aggregator, func, result):
    agg = aggregator(func)
    agg.calculate()
    assert np.array_equal(agg.target.array, np.array(result))


@pytest.fixture
def simple_aggregator(float_data):
    def get(func="max", previous_source=None):
        source = float_data([0, 5, 7])
        target = float_data([2, 0, 6])
        mapping = QueryResult(indices=np.array([0, 1, 2]), row_ptr=np.array([0, 1, 2, 3]))
        return PropertyAggregator(
            source=source,
            target=target,
            func=func,
            mapping=mapping,
            default_special_value=-1,
            previous_source=previous_source,
        )

    return get


@pytest.mark.parametrize(
    ["func", "previous_target", "previous_source", "dt", "instantiated", "result"],
    [
        ("integral", None, [0, 0, 0], 0, False, [0, 0, 0]),
        ("integral", [0, 0, 0], None, 0, False, [0, 0, 0]),
        ("integral", [0, 0, 0], [0, 0, 0], 0, False, [0, 0, 0]),
        ("integral", [0, 0, 0], [5, 0, 7], 1, False, [5, 0, 7]),
        ("integral_seconds", [0, 0, 0], [5, 0, 7], 1, False, [5, 0, 7]),
        ("integral", [5, 5, 5], [5, 0, 7], 1, True, [10, 5, 12]),
        ("integral", [0, 0, 0], [5, 0, 7], 2, False, [10, 0, 14]),
        ("integral_minutes", [0, 0, 0], [5, 0, 7], 60, False, [5, 0, 7]),
    ],
)
def test_aggregate_integral(
    simple_aggregator, func, result, dt, previous_target, previous_source, instantiated
):
    if previous_source is not None:
        previous_source = np.array(previous_source)
    agg = simple_aggregator(func, previous_source=previous_source)
    if previous_target:
        agg.target[:] = np.array(previous_target)
    if instantiated:
        agg.initialized = True
    agg.calculate(dt)
    assert np.array_equal(agg.target.array, np.array(result))
    assert np.array_equal(agg.previous_source, agg.source.array)
