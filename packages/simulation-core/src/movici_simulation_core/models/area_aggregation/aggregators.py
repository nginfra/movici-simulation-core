import typing as t

import numpy as np
from movici_geo_query.geo_query import QueryResult

from movici_simulation_core.core import UniformAttribute

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = SECONDS_PER_MINUTE * 60
SECONDS_PER_DAY = SECONDS_PER_HOUR * 24


functions: t.Dict[str, t.Tuple[t.Callable, bool]] = dict()


def aggregation_function(name: str, time_history: bool = False):
    def wrapper(func):
        functions[name] = (func, time_history)
        return func

    return wrapper


@aggregation_function("min")
def func_min(source, special, **_) -> np.ndarray:
    if len(source) == 0:
        return special
    return np.min(source)


@aggregation_function("max")
def func_max(source, special, **_) -> np.ndarray:
    if len(source) == 0:
        return special
    return np.max(source)


@aggregation_function("average")
def func_avg(source, special, weights, **_) -> np.ndarray:
    if len(source) == 0:
        return special
    return np.average(weights * source)


@aggregation_function("sum")
def func_sum(source, weights, **_) -> np.ndarray:
    return np.sum(weights * source)


@aggregation_function("integral_seconds", time_history=True)
@aggregation_function("integral", time_history=True)
def func_integral(previous_source, weights, dt, previous_target, scale=1, **_) -> np.ndarray:
    return previous_target + dt / scale * np.sum(weights * previous_source)


@aggregation_function("integral_minutes", time_history=True)
def func_integral_minutes(previous_source, weights, dt, previous_target, **_) -> np.ndarray:
    return func_integral(previous_source, weights, dt, previous_target, scale=SECONDS_PER_MINUTE)


@aggregation_function("integral_hours", time_history=True)
def func_integral_hours(previous_source, weights, dt, previous_target, **_) -> np.ndarray:
    return func_integral(previous_source, weights, dt, previous_target, scale=SECONDS_PER_HOUR)


@aggregation_function("integral_days", time_history=True)
def func_integral_days(previous_source, weights, dt, previous_target, **_) -> np.ndarray:
    return func_integral(previous_source, weights, dt, previous_target, scale=SECONDS_PER_DAY)


class AttributeAggregator:
    def __init__(
        self,
        source: UniformAttribute,
        target: UniformAttribute,
        func: str,
        mapping: QueryResult = None,
        default_special_value=-9999,
        weights: np.ndarray = None,
        previous_source: np.ndarray = None,
    ):
        self.source = source
        self.target = target
        self.function, self.time_history = functions[func]
        self.mapping = mapping
        self.default_special_value = default_special_value
        self.weights = weights
        self.previous_source = previous_source
        self.initialized = False

    def add_mapping(self, mapping: QueryResult):
        self.mapping = mapping

    def set_weights(self, weights: np.ndarray):
        self.weights = weights

    def initialize(self):
        if self.initialized:
            return
        self.initialized = True

        if self.previous_source is None:
            self.previous_source = np.zeros_like(self.source.array)

        if not self.time_history:
            return

        self.target[:] = np.zeros_like(self.target.array)

    def calculate(self, dt=None):
        self.initialize()
        self.ensure_special_value(self.target, self.default_special_value)
        if not self.mapping:
            raise RuntimeError("QueryResult not set at runtime")
        if self.weights is None:
            self.weights = np.ones(len(self.source))

        finite = ~(self.source.is_special() | self.source.is_undefined())

        for target_idx, source_indices in enumerate(self.mapping.iterate()):
            to_count = np.zeros(len(self.source), dtype=bool)
            to_count[source_indices] = True
            to_count &= finite
            self.target[target_idx] = self.function(
                source=self.source[to_count],
                previous_source=self.previous_source[to_count],
                weights=self.weights[to_count],
                dt=dt,
                previous_target=self.target[target_idx],
                special=self.target.options.special,
            )
        self.previous_source = self.source.array.copy()

    @staticmethod
    def ensure_special_value(attr, special_value):
        if attr.options.special is None:
            attr.options.special = special_value
