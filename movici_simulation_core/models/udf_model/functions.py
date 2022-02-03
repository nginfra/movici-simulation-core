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
def min_func(*arrays_or_values):
    """calculate row-wise minimum value of n arrays or values. Every array must have the same
    length in the first dimension. Values are broadcasted along the first axis
    """
    return _extreme_func(
        arrays_or_values,
        row_wise_csr=row_wise_min,
        row_wise_uniform=np.amin,
        reduce_func=np.minimum,
    )


@func("max")
def max_func(*arrays_or_values):
    """calculate row-wise maximum value of n arrays or values. Every array must have the same
    length in the first dimension. Values are broadcasted along the first axis
    """
    return _extreme_func(
        arrays_or_values,
        row_wise_csr=row_wise_max,
        row_wise_uniform=np.amax,
        reduce_func=np.maximum,
    )


def _extreme_func(arrays_or_values, row_wise_csr, row_wise_uniform, reduce_func):
    if len(arrays_or_values) < 1:
        raise TypeError("max() function requires at least one argument")
    data_type = None
    result = None
    for item in arrays_or_values:
        if isinstance(item, TrackedCSRArray):
            data_type = infer_data_type_from_array(item.data)
            item_max = row_wise_csr(item.data, item.row_ptr, empty_row=data_type.undefined)

        elif isinstance(item, np.ndarray):
            item_max = row_wise_uniform(item, axis=tuple(range(1, item.ndim)))
        else:
            item_max = item

        if result is None:
            result = item_max
        else:
            result = reduce_func(result, item_max)
    return result


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
