import numba
import numpy as np

from .core.numba_extensions import register_jitable
from .utils.unicode import largest_unicode_dtype

# NumPy 2.0 compatibility: use np.bool_ for numba compatibility, but this will work in NumPy 2.0
try:
    # Test if np.bool_ exists (NumPy < 2.0)
    BOOL_DTYPE = np.bool_
except AttributeError:
    # NumPy 2.0+ - np.bool_ is removed, use np.bool_() constructor or just bool
    BOOL_DTYPE = bool


@numba.njit(cache=True)
def rows_equal(data, row_ptr, row, rtol=1e-05, atol=1e-08, equal_nan=False):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=BOOL_DTYPE)
    for i in range(n_rows):
        data_row = get_row(data, row_ptr, i)
        rv[i] = (data_row.shape == row.shape) and np.all(
            isclose_numba(data_row, row, rtol=rtol, atol=atol, equal_nan=equal_nan)
        )
    return rv


@numba.njit(cache=True)
def rows_contain(data, row_ptr, val, rtol=1e-05, atol=1e-08, equal_nan=False):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=BOOL_DTYPE)
    for i in range(n_rows):
        rv[i] = np.any(isclose_numba(get_row(data, row_ptr, i), val, rtol, atol, equal_nan))
    return rv


@numba.njit(cache=True)
def rows_intersect(data, row_ptr, vals, rtol=1e-05, atol=1e-08, equal_nan=False):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=BOOL_DTYPE)
    for i in range(n_rows):
        data_row = get_row(data, row_ptr, i)
        for item in vals:
            if np.any(isclose_numba(data_row, item, rtol=rtol, atol=atol, equal_nan=equal_nan)):
                rv[i] = True
                break
    return rv


@numba.njit(cache=True)
def row_wise_sum(data, row_ptr):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=data.dtype)
    for i in range(n_rows):
        data_row = get_row(data, row_ptr, i)
        rv[i] = np.sum(data_row)
    return rv


def _validate_numeric_dtype(data):
    """Validate that the array has a numeric dtype."""
    if not np.issubdtype(data.dtype, np.number):
        raise TypeError("Only numeric arrays are supported")


def _validate_empty_data(data):
    """Validate that the data array is not empty."""
    if len(data) == 0:
        raise ValueError()


@numba.njit(cache=True)
def _row_wise_max_impl(data, row_ptr, empty_row=None):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=data.dtype)
    for i in range(n_rows):
        data_row = get_row(data, row_ptr, i)
        if len(data_row) == 0:
            if empty_row is not None:
                rv[i] = empty_row
            else:
                # Handle empty row case - use dtype minimum or 0
                rv[i] = 0  # Could also use np.finfo(data.dtype).min for float types
        else:
            rv[i] = np.max(data_row)
    return rv


def row_wise_max(data, row_ptr, empty_row=None):
    _validate_numeric_dtype(data)
    _validate_empty_data(data)
    return _row_wise_max_impl(data, row_ptr, empty_row)


@numba.njit(cache=True)
def _row_wise_min_impl(data, row_ptr, empty_row=None):
    n_rows = row_ptr.size - 1
    rv = np.zeros((n_rows,), dtype=data.dtype)
    for i in range(n_rows):
        data_row = get_row(data, row_ptr, i)
        if len(data_row) == 0:
            if empty_row is not None:
                rv[i] = empty_row
            else:
                # Handle empty row case - use dtype maximum or 0
                rv[i] = 0  # Could also use np.finfo(data.dtype).max for float types
        else:
            rv[i] = np.min(data_row)
    return rv


def row_wise_min(data, row_ptr, empty_row=None):
    _validate_numeric_dtype(data)
    _validate_empty_data(data)
    return _row_wise_min_impl(data, row_ptr, empty_row)


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
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
    # Handle string comparisons at Python level
    is_a_string = isinstance(a, (str, np.str_)) or (
        hasattr(a, "dtype") and a.dtype.kind in ["U", "S"]
    )
    is_b_string = isinstance(b, (str, np.str_)) or (
        hasattr(b, "dtype") and b.dtype.kind in ["U", "S"]
    )

    if is_a_string or is_b_string:
        # String comparison - use simple equality
        if dtype := largest_unicode_dtype(a, b):
            if isinstance(a, np.ndarray):
                a = np.asarray(a, dtype=dtype)
            if isinstance(b, np.ndarray):
                b = np.asarray(b, dtype=dtype)
        return a == b

    # Numeric comparison - use numba implementation
    if dtype := largest_unicode_dtype(a, b):
        if isinstance(a, np.ndarray):
            a = np.asarray(a, dtype=dtype)
        if isinstance(b, np.ndarray):
            b = np.asarray(b, dtype=dtype)
    return isclose_numba(a, b, rtol=rtol, atol=atol, equal_nan=equal_nan)


# Overload has been imported at top of file


@register_jitable
def isclose_numba(a, b, rtol=1e-05, atol=1e-08, equal_nan=False):
    # Use numpy's isclose for numeric types, equality for others
    return np.isclose(a, b, rtol, atol, equal_nan)
