from __future__ import annotations
from typing import Optional, Tuple, Union

import numpy as np

from .csr_helpers import (
    get_row,
    update_csr_array,
    slice_csr_array,
    rows_equal,
    rows_contain,
    rows_intersect,
)
from .unicode_helpers import equal_str_dtypes


class TrackedArray(np.ndarray):
    _curr: Optional[np.ndarray] = None
    _changed: Optional[np.ndarray] = None
    rtol: float
    atol: float
    equal_nan: bool

    def __new__(cls, input_array, rtol=1e-05, atol=1e-08, equal_nan=False):
        arr: TrackedArray = np.asarray(input_array).view(cls)
        arr.rtol = rtol
        arr.atol = atol
        arr.equal_nan = equal_nan
        return arr

    def __array_finalize__(self, obj):
        # __array_finalize__ is the numpy version of __init__
        self._curr = None
        if obj is not None:
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
            self._curr = self.copy()

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

    def diff(self) -> Tuple[np.ndarray, np.ndarray]:
        self._start_tracking()
        return self._curr[self.changed], self[self.changed]

    def astype(self, dtype, order="K", casting="unsafe", subok=True, copy=True):
        rv = super().astype(dtype, order=order, casting=casting, subok=subok, copy=copy)
        if self._curr:
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

    def update(self, updates: TrackedCSRArray, indices: np.ndarray, skip_value=None):
        """Update the CSRArray in place"""

        # Numba expects unicode dtypes to be of equal size, so we adjust the updates array
        if not equal_str_dtypes(self.data, updates.data):
            updates = updates.astype(self.data.dtype)

        changes = np.zeros((self.row_ptr.size - 1,), dtype=np.bool)

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
            skip_value=skip_value,
        )

        self.changed += changes

    def get_row(self, index):
        return get_row(self.data, self.row_ptr, index)

    def slice(self, indices):
        indices = np.asarray(indices)
        if indices.dtype.type == np.bool_:
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
            self.data, self.row_ptr, val, rtol=self.rtol, atol=self.atol, equal_nan=self.equal_nan
        )

    def rows_intersect(self, vals):
        """return a boolean array where the rows of `csr` contain any of the `vals` arguments"""
        return rows_intersect(
            self.data, self.row_ptr, vals, rtol=self.rtol, atol=self.atol, equal_nan=self.equal_nan
        )

    def reset(self):
        self.changed = np.zeros((self.size,), dtype=np.bool_)


TrackedArrayType = Union[TrackedArray, TrackedCSRArray]
