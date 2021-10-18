import numpy as np

from movici_simulation_core.core.schema import infer_data_type_from_array
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray
from movici_simulation_core.data_tracker.csr_helpers import (
    row_wise_sum,
    row_wise_min,
    row_wise_max,
)


def sum_func(arr):
    if isinstance(arr, TrackedCSRArray):
        return row_wise_sum(arr.data, arr.row_ptr)
    if isinstance(arr, np.ndarray):
        return np.sum(arr, axis=tuple(range(1, arr.ndim)))
    return np.sum(arr)


def min_func(arr):
    if isinstance(arr, TrackedCSRArray):
        data_type = infer_data_type_from_array(arr.data)
        return row_wise_min(arr.data, arr.row_ptr, empty_row=data_type.undefined)
    if isinstance(arr, np.ndarray):
        return np.min(arr, axis=tuple(range(1, arr.ndim)))
    return np.min(arr)


def max_func(arr):
    if isinstance(arr, TrackedCSRArray):
        data_type = infer_data_type_from_array(arr.data)
        return row_wise_max(arr.data, arr.row_ptr, empty_row=data_type.undefined)
    if isinstance(arr, np.ndarray):
        return np.max(arr, axis=tuple(range(1, arr.ndim)))
    return np.max(arr)
