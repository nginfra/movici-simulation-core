from __future__ import annotations

import typing as t

import numpy as np

from movici_simulation_core.csr import (
    csr_binop,
    get_row,
    rows_contain,
    rows_equal,
    rows_intersect,
    slice_csr_array,
    update_csr_array,
)
from movici_simulation_core.utils.unicode import equal_str_dtypes


class TrackedArray(np.ndarray):
    _curr: t.Optional[np.ndarray] = None
    _changed: t.Optional[np.ndarray] = None
    rtol: float
    atol: float
    equal_nan: bool

    def __new__(cls, input_array, rtol=1e-05, atol=1e-08, equal_nan=False):
        arr: TrackedArray = np.asarray(input_array).view(cls)
        arr.rtol = rtol
        arr.atol = atol
        arr.equal_nan = equal_nan
        if isinstance(input_array, TrackedArray):
            arr._curr = input_array._curr
        return arr

    def __array_finalize__(self, obj):
        # __array_finalize__ is the numpy version of __init__. `self` is already instantiated
        # and we get `obj` as an optional source object from which this array was created (such as
        # during slicing)
        if obj is not None:
            self._curr = getattr(obj, "_curr", None)
            self.atol = getattr(obj, "atol", 1e-05)
            self.rtol = getattr(obj, "rtol", 1e-08)
            self.equal_nan = getattr(obj, "equal_nan", False)
        self.reset()

    def __getitem__(self, item) -> TrackedArray:
        self._start_tracking()
        return super().__getitem__(item)

    def __setitem__(self, key, value):
        self._start_tracking()
        super().__setitem__(key, value)

    def _start_tracking(self):
        self._changed = None
        if self._curr is None:
            self._curr = np.array(self)

    @property
    def changed(self):
        if self._changed is not None:
            return self._changed

        if self._curr is None:
            rv = np.zeros_like(self.data, dtype=bool)

        elif np.issubdtype(self.dtype, np.floating):
            rv = ~np.isclose(
                self, self._curr, rtol=self.rtol, atol=self.atol, equal_nan=self.equal_nan
            )
        else:
            rv = self._curr != self
        self._changed = rv
        return rv

    def reset(self):
        self._curr = None
        self._changed = None

    def diff(self) -> t.Tuple[np.ndarray, np.ndarray]:
        self._start_tracking()
        return self._curr[self.changed], self[self.changed]

    def astype(self, dtype, order="K", casting="unsafe", subok=True, copy=True):
        """"""
        rv = super().astype(dtype, order=order, casting=casting, subok=subok, copy=copy)
        if self._curr is not None:
            rv._curr = self._curr.astype(
                dtype, order=order, casting=casting, subok=subok, copy=copy
            )
        return rv


class TrackedCSRArray:
    data: np.ndarray
    row_ptr: np.ndarray
    changed: np.ndarray
    size: int

    def __init__(self, data, row_ptr, rtol=1e-05, atol=1e-08, equal_nan=False):
        self.data = np.asarray(data)
        self.row_ptr = np.asarray(row_ptr)
        self.size = self.row_ptr.size - 1
        self.rtol = rtol
        self.atol = atol
        self.equal_nan = equal_nan
        self.reset()

    def update(self, updates: TrackedCSRArray, indices: np.ndarray):
        """Update the CSRArray in place"""

        # Numba expects unicode dtypes to be of equal size, so we adjust the updates array
        if not equal_str_dtypes(self.data, updates.data):
            updates = updates.astype(self.data.dtype)

        changes = np.zeros((self.row_ptr.size - 1,), dtype=bool)

        self.data, self.row_ptr = update_csr_array(
            data=self.data,
            row_ptr=self.row_ptr,
            upd_data=updates.data,
            upd_row_ptr=updates.row_ptr,
            upd_indices=np.asarray(indices),
            changes=changes,
            rtol=self.rtol,
            atol=self.atol,
            equal_nan=self.equal_nan,
        )

        self.changed += changes

    def get_row(self, index):
        return get_row(self.data, self.row_ptr, index)

    def slice(self, indices):
        indices = np.asarray(indices)
        if indices.dtype.type in [bool, np.bool_]:
            indices = np.flatnonzero(indices)
        slice_data, slice_row_ptr = slice_csr_array(
            self.data, self.row_ptr, np.asarray(indices, dtype=int)
        )
        return TrackedCSRArray(slice_data, slice_row_ptr)

    def astype(self, dtype, order="K", casting="unsafe", subok=True, copy=True):
        data = self.data.astype(dtype, order=order, casting=casting, subok=subok, copy=copy)
        rv = TrackedCSRArray(
            data, self.row_ptr, rtol=self.rtol, atol=self.atol, equal_nan=self.equal_nan
        )
        rv.changed = self.changed
        return rv

    def rows_equal(self, row):
        """return a boolean array where the rows of `csr` equal the `row` argument"""
        return rows_equal(
            self.data,
            self.row_ptr,
            row.astype(self.data.dtype),
            rtol=self.rtol,
            atol=self.atol,
            equal_nan=self.equal_nan,
        )

    def rows_contain(self, val):
        """return a boolean array where the rows of `csr` contain the `val` argument"""

        return rows_contain(
            self.data,
            self.row_ptr,
            np.array(val, dtype=self.data.dtype),
            rtol=self.rtol,
            atol=self.atol,
            equal_nan=self.equal_nan,
        )

    def rows_intersect(self, vals):
        """return a boolean array where the rows of `csr` contain any of the `vals` arguments"""
        return rows_intersect(
            self.data, self.row_ptr, vals, rtol=self.rtol, atol=self.atol, equal_nan=self.equal_nan
        )

    def reset(self):
        self.changed = np.zeros((self.size,), dtype=bool)

    def __bin_op__(self, other, op):
        if isinstance(other, TrackedCSRArray):
            if not np.all(self.row_ptr == other.row_ptr):
                raise ValueError("row_ptr arrays must be equal")
            return TrackedCSRArray(data=op(self.data, other.data), row_ptr=self.row_ptr.copy())
        try:
            other = np.asarray(other)
            if other.ndim == 1 and len(other) == len(self.row_ptr) - 1:
                return TrackedCSRArray(
                    data=csr_binop(self.data, self.row_ptr, other, op),
                    row_ptr=self.row_ptr.copy(),
                )
            return TrackedCSRArray(data=op(self.data, other), row_ptr=self.row_ptr.copy())
        except TypeError:
            return NotImplemented

    def __add__(self, other):
        return self.__bin_op__(other, np.add)

    def __sub__(self, other):
        return self.__bin_op__(other, np.subtract)

    def __mul__(self, other):
        return self.__bin_op__(other, np.multiply)

    def __truediv__(self, other):
        return self.__bin_op__(other, np.divide)

    def copy(self):
        return TrackedCSRArray(
            data=self.data.copy(),
            row_ptr=self.row_ptr.copy(),
            rtol=self.rtol,
            atol=self.atol,
            equal_nan=self.equal_nan,
        )

    def as_matrix(self):
        if self.size == 0:
            return np.ndarray((0, 0))
        if self.size == 1:
            return self.data.copy()[np.newaxis, :]

        row_length = self.row_ptr[1] - self.row_ptr[0]
        if not np.all(np.diff(self.row_ptr) == row_length):
            raise ValueError(
                "Can only convert CSR array to matrix when all rows have an equal length"
            )

        return self.data.copy().reshape((self.size, row_length))

    def update_from_matrix(self, matrix: np.ndarray):
        """Update the csr-array from a 2D matrix. The matrix number of rows must match the
        csr-array's number of rows
        """
        shape = matrix.shape

        if len(shape) != 2 or shape[0] != self.size:
            raise ValueError("Can only update a CSR array with a matrix of equal number of rows")

        if len(self.data) == matrix.size and np.all(np.diff(self.row_ptr) == shape[1]):
            # self.data is in the correct shape
            self._update_from_matrix_inplace(matrix)
        else:
            as_csr = matrix_to_csr(matrix)
            self.update(as_csr, indices=np.arange(self.size))

    def _update_from_matrix_inplace(self, matrix):
        shape = matrix.shape
        new_data = matrix.flatten()

        # Since we update the data directly, changes are not calculated automatically
        # and we have to calculate them ourselves
        changed = ~np.isclose(
            self.data,
            new_data,
            rtol=self.rtol,
            atol=self.atol,
            equal_nan=self.equal_nan,
        ).reshape(shape)
        self.data = new_data
        self.changed += np.amax(changed, axis=1)


TrackedArrayType = t.Union[TrackedArray, TrackedCSRArray]


def matrix_to_csr(matrix: np.ndarray):
    """convert a 2d array to a TrackedCSRArray"""
    row_ptr = np.arange(0, matrix.size + 1, matrix.shape[1])
    data = matrix.flatten()
    return TrackedCSRArray(data, row_ptr)
