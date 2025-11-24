import functools
import typing as t

import numba
import numpy as np
from numba.core.types import number_domain

# required for proper np.isclose support in numpy
from .core import numba_extensions  # noqa F401


@functools.lru_cache(None)
def float_compare(rtol=1e-5, atol=1e-8, equal_nan=True):
    """factory function for creating a float compare function"""

    @numba.njit(cache=True)
    def impl(a, b):
        return np.isclose(a, b, rtol, atol, equal_nan)

    return impl


@numba.njit(cache=True)
def compare_scalar(a, b):
    """compare function for comparing an array against a scalar
    :param a: a numpy array
    :param b: a scalar
    """
    a = np.asarray(a)
    rv = np.zeros_like(a, dtype=np.bool_)
    for i in range(a.size):
        rv.flat[i] = a.flat[i] == b
    return rv


@numba.njit(cache=True)
def compare_array(a, b):
    """compare function when both a and b are numpy arrays (and not float arrays)"""
    return a == b


@numba.njit(cache=True)
def rows_equal(data, row_ptr, row, compare):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=np.bool_)
    for i in range(n_rows):
        data_row = get_row(data, row_ptr, i)
        rv[i] = (data_row.shape == row.shape) and np.all(compare(data_row, row))
    return rv


@numba.njit(cache=True)
def rows_contain(data, row_ptr, val, compare):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=np.bool_)
    for i in range(n_rows):
        rv[i] = np.any(compare(get_row(data, row_ptr, i), val))
    return rv


@numba.njit(cache=True)
def rows_intersect(data, row_ptr, vals, compare):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=np.bool_)
    for i in range(n_rows):
        data_row = get_row(data, row_ptr, i)
        for item in vals:
            if np.any(compare(data_row, item)):
                rv[i] = True
                break
    return rv


@numba.njit(cache=True)
def row_wise_sum(data, row_ptr):
    return reduce_rows(data, row_ptr, np.sum)


@numba.njit()
def row_wise_max(data, row_ptr, empty_row=None):
    if empty_row is None:
        return reduce_rows(data, row_ptr, np.max)

    return reduce_rows_with_substitute(data, row_ptr, _substituted_max, empty_row)


@numba.njit()
def row_wise_min(data, row_ptr, empty_row=None):
    if empty_row is None:
        return reduce_rows(data, row_ptr, np.min)

    return reduce_rows_with_substitute(data, row_ptr, _substituted_min, empty_row)


# cannot cache this function because numba complains about not being able to pickle a closure
@numba.njit()
def reduce_rows_with_substitute(data, row_ptr, func, substitute):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=data.dtype)
    for i in range(n_rows):
        data_row = get_row(data, row_ptr, i)
        rv[i] = func(data_row, substitute)
    return rv


# cannot cache this function because numba complains about not being able to pickle a closure
@numba.njit()
def reduce_rows(data, row_ptr, func):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=data.dtype)
    for i in range(n_rows):
        data_row = get_row(data, row_ptr, i)
        rv[i] = func(data_row)
    return rv


@numba.njit(cache=True)
def _substituted_max(data, empty_row):
    if len(data) == 0:
        return empty_row
    return np.max(data)


@numba.njit(cache=True)
def _substituted_min(data, empty_row):
    if len(data) == 0:
        return empty_row
    return np.min(data)


def csr_binop(data, row_ptr, operand, operator):
    """Perform binary operation ``operator`` rowwise on a csr array, the operand must be a 1d array
    of length equal to the number of rows in the csr array
    """
    if len(operand) != len(row_ptr) - 1:
        raise ValueError("Can only add to CSR arrays if array length equals number of rows")
    rv = np.zeros_like(data)

    for idx, val in enumerate(operand):
        begin, end = row_ptr[idx], row_ptr[idx + 1]

        rv[begin:end] = operator(data[begin:end], val)
    return rv


def assert_numeric_array(arr):
    if getattr(arr, "dtype", None) not in number_domain:
        raise TypeError("Only numeric arrays are supported")


@numba.njit(cache=True)
def update_csr_array(
    data,
    row_ptr,
    upd_data,
    upd_row_ptr,
    upd_indices,
    compare,
    changes=None,
):
    """Update a csr array (`data` and `row_ptr`) in place with an update csr array (`upd_data`
    and `upd_row_ptr` at the locations `upd_indices`. `data` and `upd_data` must be of the same
    dtype and may only differ in shape in the first dimension. Can optionally track changes by
    `changes` output argument as an boolean array of zeros that has the length equal to the
    number of rows in of the data csr array ( `len( row_ptr)-1`). When tracking changes `rtol`,
    `atol` and `equal_nan` mean the same as in np.isclose
    """
    n_rows = row_ptr.size - 1

    row_lengths = np.diff(row_ptr)
    row_lengths[upd_indices] = np.diff(upd_row_ptr)

    new_data, new_row_ptr = get_new_csr_array(row_lengths, data.dtype, data.shape[1:])

    valid_old_rows = np.ones((n_rows,), dtype=np.bool_)
    valid_old_rows[upd_indices] = False
    valid_old_rows = valid_old_rows.nonzero()[0]

    for i in valid_old_rows:
        set_row(new_data, new_row_ptr, i, get_row(data, row_ptr, i))

    for upd_idx, pos in enumerate(upd_indices):
        old_row = get_row(data, row_ptr, pos)
        new_row = get_row(upd_data, upd_row_ptr, upd_idx)

        if changes is not None:
            is_equal = (old_row.shape == new_row.shape) and np.all(compare(old_row, new_row))
            changes[pos] = not is_equal
        set_row(new_data, new_row_ptr, pos, new_row)
    return new_data, new_row_ptr


@numba.njit(cache=True)
def remove_undefined_csr(
    data: np.ndarray,
    row_ptr: np.ndarray,
    indices: np.ndarray,
    undefined,
    num_undefined,
    new_data_shape,
    compare,
) -> t.Tuple[np.ndarray, np.ndarray, np.ndarray]:
    new_data = np.empty(new_data_shape, dtype=data.dtype)
    new_row_ptr = np.empty(len(row_ptr) - num_undefined, dtype=row_ptr.dtype)
    new_indices = np.empty(len(indices) - num_undefined, dtype=indices.dtype)

    new_row_ptr[0] = 0
    current_index = 0

    for i, index in enumerate(indices):
        idx = row_ptr[i]
        idx2 = row_ptr[i + 1]
        data_field = data[idx:idx2]
        if len(data_field) == 1 and np.all(compare(data_field, undefined)):
            continue
        new_row_ptr[current_index + 1] = new_row_ptr[current_index] + len(data_field)
        new_data[new_row_ptr[current_index] : new_row_ptr[current_index + 1]] = data_field
        new_indices[current_index] = index
        current_index += 1

    return new_data, new_row_ptr, new_indices


@numba.njit(cache=True)
def get_row(data, row_ptr, index):
    return data[row_ptr[index] : row_ptr[index + 1]]


@numba.njit(cache=True)
def set_row(data, row_ptr, index, new_row):
    """Set a new row on at the specific index of the csr_array. WARNING: the length of the new row
    must be allocated in the data array, otherwise this function may override other rows
    """
    data[row_ptr[index] : row_ptr[index + 1], ...] = new_row


@numba.njit(cache=True)
def slice_csr_array(data, row_ptr, indices):
    slice_data, slice_row_ptr = get_new_csr_array(
        row_lengths=np.diff(row_ptr)[indices],
        dtype=data.dtype,
        secondary_shape=data.shape[1:],
    )
    for slice_idx, data_idx in enumerate(indices):
        set_row(slice_data, slice_row_ptr, slice_idx, get_row(data, row_ptr, data_idx))
    return slice_data, slice_row_ptr


@numba.njit(cache=True)
def get_new_csr_array(row_lengths, dtype, secondary_shape):
    row_ptr = np.hstack((np.array([0]), np.cumsum(row_lengths)))
    data = np.empty((row_ptr[-1], *secondary_shape), dtype=dtype)
    return data, row_ptr


@numba.njit(cache=True)
def generate_update(data, row_ptr, mask, changed, undefined):
    undefined_indices = mask & ~changed
    secondary_shape = data.shape[1:]
    row_lengths = np.diff(row_ptr)
    row_lengths[undefined_indices] = 1
    upd_data, upd_row_ptr = get_new_csr_array(
        row_lengths=row_lengths[mask],
        dtype=data.dtype,
        secondary_shape=secondary_shape,
    )
    for upd_idx, data_idx in enumerate(np.flatnonzero(mask)):
        if changed[data_idx]:
            val = get_row(data, row_ptr, data_idx)
        else:
            val = np.full((1, *secondary_shape), fill_value=undefined, dtype=data.dtype)
        set_row(upd_data, upd_row_ptr, upd_idx, val)

    return upd_data, upd_row_ptr
