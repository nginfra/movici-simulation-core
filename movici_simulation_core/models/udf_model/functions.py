import numpy as np

from movici_simulation_core.core.schema import infer_data_type_from_array
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray
from movici_simulation_core.data_tracker.csr_helpers import (
    row_wise_sum,
    row_wise_min,
    row_wise_max,
)
from movici_simulation_core.data_tracker.data_format import is_undefined_uniform, is_undefined_csr

functions = {}


def func(name: str):
    def decorator(f):
        functions[name] = f
        return f

    return decorator


@func("sum")
def sum_func(arr):
    if isinstance(arr, TrackedCSRArray):
        return row_wise_sum(arr.data, arr.row_ptr)
    if isinstance(arr, np.ndarray):
        return np.sum(arr, axis=tuple(range(1, arr.ndim)))
    return np.sum(arr)


@func("min")
def min_func(arr):
    if isinstance(arr, TrackedCSRArray):
        data_type = infer_data_type_from_array(arr.data)
        return row_wise_min(arr.data, arr.row_ptr, empty_row=data_type.undefined)
    if isinstance(arr, np.ndarray):
        return np.min(arr, axis=tuple(range(1, arr.ndim)))
    return np.min(arr)


@func("max")
def max_func(arr):
    if isinstance(arr, TrackedCSRArray):
        data_type = infer_data_type_from_array(arr.data)
        return row_wise_max(arr.data, arr.row_ptr, empty_row=data_type.undefined)
    if isinstance(arr, np.ndarray):
        return np.max(arr, axis=tuple(range(1, arr.ndim)))
    return np.max(arr)


@func("default")
def default_func(arr, default_val):
    if isinstance(arr, np.ndarray):
        data_type = infer_data_type_from_array(arr)
        undefined = is_undefined_uniform(arr, data_type)
        rv = arr.copy()
        rv[undefined] = (
            default_val[undefined] if isinstance(default_val, np.ndarray) else default_val
        )
        return rv
    if isinstance(arr, TrackedCSRArray):
        data_type = infer_data_type_from_array(arr.data)
        undefined = np.flatnonzero(is_undefined_csr(arr, data_type))
        default_values = TrackedCSRArray(
            data=np.full_like(undefined, fill_value=default_val, dtype=arr.data.dtype),
            row_ptr=np.arange(len(undefined) + 1),
        )
        rv = arr.copy()
        rv.update(default_values, undefined)
        return rv
