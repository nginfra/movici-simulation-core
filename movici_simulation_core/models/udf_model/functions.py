import typing as t

import numpy as np

from movici_simulation_core.core.arrays import TrackedCSRArray
from movici_simulation_core.core.data_format import is_undefined_csr, is_undefined_uniform
from movici_simulation_core.core.schema import infer_data_type_from_array
from movici_simulation_core.csr import csr_binop, row_wise_max, row_wise_min, row_wise_sum

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
    """
    calculates extreme (ie min or max) for multiple inputs. Result shape depends on first input.
    Rules:

    - for a single entry (array), reduce by all axes except axis 0
    - for multiple inputs, calculate the element wise minimum:
      min([1,2,3], [4,1,2], 1.5) == [1, 1, 1.5]
      min([[1,2],[3], []], 2) == [[1,2],[2],[]]
      min([[1,2],[3], []], [1.5, 2, 0]) == [[1,1.5],[2],[]]
      min([[1,2],[3], []], [1.5, 2, 0], 1.7) == [[1,1.5],[1.7],[]]


    :param arrays_or_values: multiple operands to perform the min/max calculation
    :param row_wise_csr:
    :param row_wise_uniform:
    :param reduce_func:
    :return:
    """
    if len(arrays_or_values) < 1:
        raise TypeError("max() function requires at least one argument")

    item = arrays_or_values[0]

    if len(arrays_or_values) == 1:
        if isinstance(item, TrackedCSRArray):
            data_type = infer_data_type_from_array(item.data)
            return row_wise_csr(item.data, item.row_ptr, empty_row=data_type.undefined)
        elif isinstance(item, np.ndarray):
            return row_wise_uniform(item, axis=tuple(range(1, item.ndim)))
        else:
            # item is a scalar, which cannot be reduced
            return item

    if isinstance(item, TrackedCSRArray):
        working_func = _extreme_func_csr
    elif isinstance(item, np.ndarray):
        working_func = _extreme_func_uniform
    else:
        raise ValueError(
            "min/max functions should have an attribute as their first argument, not a scalar"
        )

    result = item

    for item in arrays_or_values[1:]:
        result = working_func(result, item, reduce_func)
    return result


def _extreme_func_csr(
    csr_array: TrackedCSRArray, other: t.Union[np.ndarray, float, int], extreme_func
):
    if isinstance(other, np.ndarray):
        data = csr_binop(csr_array.data, csr_array.row_ptr, other, extreme_func)
    else:
        data = extreme_func(csr_array.data, other)
    return TrackedCSRArray(data, row_ptr=csr_array.row_ptr)


def _extreme_func_uniform(
    array: np.ndarray, other: t.Union[np.ndarray, TrackedCSRArray, float, int], extreme_func
):
    return extreme_func(array, other)


@func("default")
def default_func(
    arr: t.Union[TrackedCSRArray, np.ndarray],
    default_val: t.Union[float, TrackedCSRArray, np.ndarray],
):
    if isinstance(arr, np.ndarray):
        if isinstance(default_val, TrackedCSRArray):
            raise TypeError("Cannot assign default CSR data to a Uniform attribute")
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
        if isinstance(default_val, (float, int, bool)):
            default_values = TrackedCSRArray(
                data=np.full_like(undefined, fill_value=default_val, dtype=arr.data.dtype),
                row_ptr=np.arange(len(undefined) + 1),
            )

        elif isinstance(default_val, np.ndarray):
            default_values = TrackedCSRArray(
                data=default_val[undefined],
                row_ptr=np.arange(len(undefined) + 1),
            )

        elif isinstance(default_val, TrackedCSRArray):
            default_values = default_val.slice(undefined)
        else:
            raise TypeError(f"Usupported default value of type {type(default_val)}")

        rv = arr.copy()
        rv.update(default_values, undefined)
        return rv
