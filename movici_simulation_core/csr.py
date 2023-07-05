import typing as t

import numba
import numpy as np
from numba.core.types import complex_domain, number_domain, real_domain
from numba.np.numpy_support import type_can_asarray

from .core.numba_extensions import generated_jit
from .utils.unicode import largest_unicode_dtype


@numba.njit(cache=True)
def rows_equal(data, row_ptr, row, rtol=1e-05, atol=1e-08, equal_nan=False):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=np.bool_)
    for i in range(n_rows):
        data_row = get_row(data, row_ptr, i)
        rv[i] = (data_row.shape == row.shape) and np.all(
            isclose_numba(data_row, row, rtol=rtol, atol=atol, equal_nan=equal_nan)
        )
    return rv


@numba.njit(cache=True)
def rows_contain(data, row_ptr, val, rtol=1e-05, atol=1e-08, equal_nan=False):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=np.bool_)
    for i in range(n_rows):
        rv[i] = np.any(isclose_numba(get_row(data, row_ptr, i), val, rtol, atol, equal_nan))
    return rv


@numba.njit(cache=True)
def rows_intersect(data, row_ptr, vals, rtol=1e-05, atol=1e-08, equal_nan=False):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=np.bool_)
    for i in range(n_rows):
        data_row = get_row(data, row_ptr, i)
        for item in vals:
            if np.any(isclose_numba(data_row, item, rtol=rtol, atol=atol, equal_nan=equal_nan)):
                rv[i] = True
                break
    return rv


@generated_jit
def row_wise_sum(data, row_ptr):
    assert_numeric_array(data)

    def impl(data, row_ptr):
        return reduce_rows(data, row_ptr, np.sum)

    return impl


@generated_jit
def row_wise_max(data, row_ptr, empty_row=None):
    assert_numeric_array(data)

    def impl(data, row_ptr, empty_row=None):

        if empty_row is None:
            return reduce_rows(data, row_ptr, np.max)

        return reduce_rows(data, row_ptr, _substituted_max, empty_row)

    return impl


@generated_jit
def row_wise_min(data, row_ptr, empty_row=None):
    assert_numeric_array(data)

    def impl(data, row_ptr, empty_row=None):

        if empty_row is None:
            return reduce_rows(data, row_ptr, np.min)

        return reduce_rows(data, row_ptr, _substituted_min, empty_row)

    return impl


@numba.njit(cache=True)
def reduce_rows(data, row_ptr, func, *args):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=data.dtype)
    for i in range(n_rows):
        data_row = get_row(data, row_ptr, i)
        rv[i] = func(data_row, *args)
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
    changes=None,
    rtol=1e-05,
    atol=1e-08,
    equal_nan=False,
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
            is_equal = (old_row.shape == new_row.shape) and np.all(
                isclose_numba(old_row, new_row, rtol, atol, equal_nan)
            )
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
        if len(data_field) == 1 and np.all(isclose_numba(data_field, undefined, equal_nan=True)):
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


def isclose(a, b, rtol=1e-05, atol=1e-08, equal_nan=False):
    """Versatile function to determine whether two arrays, or an array and a value are close.
    Uses `np.isclose` for numeric values and arrays, and custom implementations for
    string and unicode arrays. This converts unicode arrays so that they are of uniform size and
    can be properly used in numba jit-compiled functions
    """
    if dtype := largest_unicode_dtype(a, b):
        if isinstance(a, np.ndarray):
            a = np.asarray(a, dtype=dtype)
        if isinstance(b, np.ndarray):
            b = np.asarray(b, dtype=dtype)
    return isclose_numba(a, b, rtol=rtol, atol=atol, equal_nan=equal_nan)


@generated_jit(cache=True, nopython=True)
def isclose_numba(a, b, rtol=1e-05, atol=1e-08, equal_nan=False):
    inexact_domain = real_domain | complex_domain
    if (getattr(a, "dtype", None) in inexact_domain or a in inexact_domain) and (
        getattr(b, "dtype", None) in inexact_domain or b in inexact_domain
    ):

        def impl(a, b, rtol=1e-05, atol=1e-08, equal_nan=False):
            return np.isclose(a, b, rtol, atol, equal_nan)

    elif type_can_asarray(a) and not type_can_asarray(b):

        def impl(a, b, rtol=1e-05, atol=1e-08, equal_nan=False):
            a = np.asarray(a)
            rv = np.zeros_like(a, dtype=np.bool_)
            for i in range(a.size):
                rv.flat[i] = a.flat[i] == b
            return rv

    elif type_can_asarray(b) and not type_can_asarray(a):

        def impl(a, b, rtol=1e-05, atol=1e-08, equal_nan=False):
            b = np.asarray(b)
            rv = np.zeros_like(b, dtype=np.bool_)
            for i in range(b.size):
                rv.flat[i] = b.flat[i] == a
            return rv

    else:

        def impl(a, b, rtol=1e-05, atol=1e-08, equal_nan=False):
            return a == b

    return impl
