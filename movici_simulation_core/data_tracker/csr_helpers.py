import numba
import numpy as np
from numba.core.types import real_domain, complex_domain
from numba.np.numpy_support import type_can_asarray

from .numba_extensions import generated_jit


@numba.njit(cache=True)
def rows_equal(data, row_ptr, row, rtol=1e-05, atol=1e-08, equal_nan=False):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=np.bool_)
    for i in range(n_rows):
        rv[i] = np.all(
            isclose(get_row(data, row_ptr, i), row, rtol=rtol, atol=atol, equal_nan=equal_nan)
        )
    return rv


@numba.njit(cache=True)
def rows_contain(data, row_ptr, val, rtol=1e-05, atol=1e-08, equal_nan=False):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=np.bool_)
    for i in range(n_rows):
        rv[i] = np.any(isclose(get_row(data, row_ptr, i), val, rtol, atol, equal_nan))
    return rv


@numba.njit(cache=True)
def rows_intersect(data, row_ptr, vals, rtol=1e-05, atol=1e-08, equal_nan=False):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=np.bool_)
    for i in range(n_rows):
        data_row = get_row(data, row_ptr, i)
        for item in vals:
            if np.any(isclose(data_row, item, rtol=rtol, atol=atol, equal_nan=equal_nan)):
                rv[i] = True
                break
    return rv


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
    skip_value=None,
):
    """Update a csr array (`data` and `row_ptr`) in place with an update csr array (`upd_data`
    and `upd_row_ptr` at the locations `upd_indices`. `data` and `upd_data` must be of the same
    dtype and may only differ in shape in the first dimension. Can optionally track changes by
    `changes` output argument as an boolean array of zeros that has the length equal to the
    number of rows in of the data csr array ( `len( row_ptr)-1`). When tracking changes `rtol`,
    `atol` and `equal_nan` mean the same as in np.isclose

    skip_value may be given to skip updating a row when the update row matches the skip_value
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

        if skip_value is not None and len(new_row) == 1 and new_row[0] == skip_value:
            continue

        if changes is not None:
            is_equal = (old_row.shape == new_row.shape) and np.all(
                isclose(old_row, new_row, rtol, atol, equal_nan)
            )
            changes[pos] = not is_equal
        set_row(new_data, new_row_ptr, pos, new_row)
    return new_data, new_row_ptr


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


@generated_jit(cache=True)
def isclose(a, b, rtol=1e-05, atol=1e-08, equal_nan=False):
    """Versatile function to determine whether two arrays, or an array and a value are close.
    Uses `np.isclose` for numeric values and arrays, and custom implementations for
    string and unicode arrays. When using this function for string comparisons,
    this function may be slower than expected because numba may fall back to python
    mode
    """
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
