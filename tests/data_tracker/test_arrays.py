import operator

import numpy as np
import pytest

from movici_simulation_core.data_tracker.arrays import TrackedCSRArray, TrackedArray
from movici_simulation_core.data_tracker.property import ensure_csr_data


def assert_equal_csr_arrays(a, b):
    assert np.array_equal(a.data, b.data)
    assert np.array_equal(a.row_ptr, b.row_ptr)


@pytest.mark.parametrize(
    ["array", "updates", "indices", "expected"],
    [
        (
            TrackedCSRArray(np.array([1, 2, 3, 4, 5, 6, 7]), np.array([0, 3, 6, 7])),
            TrackedCSRArray(np.array([8, 4]), np.array([0, 2])),
            [1],
            TrackedCSRArray(np.array([1, 2, 3, 8, 4, 7]), np.array([0, 3, 5, 6])),
        ),
        (
            TrackedCSRArray(np.array([1, 2, 3, 4, 5, 6, 7]), np.array([0, 3, 6, 7])),
            TrackedCSRArray(np.array([9, 7, 4, 3]), np.array([0, 4])),
            [1],
            TrackedCSRArray(np.array([1, 2, 3, 9, 7, 4, 3, 7]), np.array([0, 3, 7, 8])),
        ),
        (
            TrackedCSRArray(np.array([1, 2, 3, 4, 5, 6, 7]), np.array([0, 3, 6, 7])),
            TrackedCSRArray(np.array([9, 7, 4, 3, 2, 1]), np.array([0, 4, 6])),
            [0, 2],
            TrackedCSRArray(np.array([9, 7, 4, 3, 4, 5, 6, 2, 1]), np.array([0, 4, 7, 9])),
        ),
        (
            TrackedCSRArray(np.array([], dtype=int), np.array([0, 0])),
            TrackedCSRArray(np.array([9, 7, 4, 3]), np.array([0, 4])),
            [0],
            TrackedCSRArray(np.array([9, 7, 4, 3]), np.array([0, 4])),
        ),
        (
            TrackedCSRArray(np.array([1, 2, 3, 4, 5, 6, 7]), np.array([0, 3, 6, 7])),
            TrackedCSRArray(np.array([], dtype=int), np.array([0, 0])),
            [1],
            TrackedCSRArray(np.array([1, 2, 3, 7]), np.array([0, 3, 3, 4])),
        ),
        (
            TrackedCSRArray(np.array([1.0, 2.0]), np.array([0, 2])),
            TrackedCSRArray(np.array([3.0]), np.array([0, 1])),
            [0],
            TrackedCSRArray(np.array([3.0]), np.array([0, 1])),
        ),
        (
            TrackedCSRArray(np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float), np.array([0, 1, 2])),
            TrackedCSRArray(np.array([[2.0, 1.0]], dtype=float), np.array([0, 1])),
            [0],
            TrackedCSRArray(np.array([[2.0, 1.0], [3.0, 4.0]], dtype=float), np.array([0, 1, 2])),
        ),
    ],
)
def test_update_csr_array(array, updates, indices, expected):
    array.update(updates, np.asarray(indices, dtype=int))
    assert_equal_csr_arrays(array, expected)


@pytest.mark.parametrize(
    ["csr", "indices", "expected"],
    [
        (
            TrackedCSRArray(
                np.array([1, 2, 2, 3, 3, 3, 4]),
                np.array([0, 1, 3, 6, 7]),
            ),
            [1, 2],
            TrackedCSRArray(np.array([2, 2, 3, 3, 3]), np.array([0, 2, 5])),
        ),
        (
            TrackedCSRArray(
                np.array([1, 2, 2, 3, 3, 3, 4]),
                np.array([0, 1, 3, 6, 7]),
            ),
            [],
            TrackedCSRArray(np.array([], dtype=int), np.array([0])),
        ),
        (
            TrackedCSRArray(
                np.array([1, 2, 2, 3, 3, 3, 4]),
                np.array([0, 1, 3, 6, 7]),
            ),
            [0, 2],
            TrackedCSRArray(np.array([1, 3, 3, 3]), np.array([0, 1, 4])),
        ),
        (
            TrackedCSRArray(
                np.array([1, 2, 3]),
                np.array([0, 1, 3]),
            ),
            [False, True],
            TrackedCSRArray(np.array([2, 3]), np.array([0, 2])),
        ),
    ],
)
def test_slice_csr_array(csr, indices, expected):
    result = csr.slice(indices)
    assert_equal_csr_arrays(expected, result)


def test_update_with_smaller_string():
    csr = TrackedCSRArray(np.array(["longer_string"]), np.array([0, 1]))
    upd = TrackedCSRArray(np.array(["string"]), [0, 1])
    csr.update(upd, np.array([0]))
    assert_equal_csr_arrays(csr, upd)


@pytest.mark.parametrize(
    ["csr", "upd", "upd_idx", "expected"],
    [
        (
            TrackedCSRArray(np.array([1, 2, 3]), np.array([0, 1, 3])),
            TrackedCSRArray(np.array([8, 4]), np.array([0, 2])),
            [0],
            np.array([True, False]),
        ),
        (
            TrackedCSRArray(np.array([1, 2, 3]), np.array([0, 1, 3])),
            TrackedCSRArray(np.array([8]), np.array([0, 1])),
            [0],
            np.array([True, False]),
        ),
        (
            TrackedCSRArray(np.array([1, 2, 3]), np.array([0, 1, 3])),
            TrackedCSRArray(np.array([2, 3]), np.array([0, 2])),
            [1],
            np.array([False, False]),
        ),
        (
            TrackedCSRArray(np.array([1, 2, 3]), np.array([0, 1, 3])),
            TrackedCSRArray(np.array([1 + 1e-12]), np.array([0, 1])),
            [0],
            np.array([False, False]),
        ),
        (
            TrackedCSRArray(np.array([1.0]), np.array([0, 1])),
            TrackedCSRArray(np.array([1.001]), np.array([0, 1])),
            [0],
            np.array([True]),
        ),
        (
            TrackedCSRArray(np.array([1.0]), np.array([0, 1]), rtol=1e-2),
            TrackedCSRArray(np.array([1.001]), np.array([0, 1])),
            [0],
            np.array([False]),
        ),
        (
            TrackedCSRArray(np.array([np.nan]), np.array([0, 1]), equal_nan=True),
            TrackedCSRArray(np.array([np.nan]), np.array([0, 1])),
            [0],
            np.array([False]),
        ),
        (
            TrackedCSRArray(np.array([np.nan]), np.array([0, 1]), equal_nan=False),
            TrackedCSRArray(np.array([np.nan]), np.array([0, 1])),
            [0],
            np.array([True]),
        ),
        (
            TrackedCSRArray(np.array([0, np.nan]), np.array([0, 2]), equal_nan=False),
            TrackedCSRArray(np.array([np.nan, np.nan]), np.array([0, 2])),
            [0],
            np.array([True]),
        ),
        (
            TrackedCSRArray(np.array([0, np.nan]), np.array([0, 2]), equal_nan=True),
            TrackedCSRArray(np.array([np.nan, np.nan]), np.array([0, 2])),
            [0],
            np.array([True]),
        ),
        (
            TrackedCSRArray(np.array(["aa", "b"]), np.array([0, 2])),
            TrackedCSRArray(np.array(["aa", "b"]), np.array([0, 2])),
            [0],
            np.array([False]),
        ),
        (
            TrackedCSRArray(np.array(["aa", "b"]), np.array([0, 2])),
            TrackedCSRArray(np.array(["aa", "c"]), np.array([0, 2])),
            [0],
            np.array([True]),
        ),
    ],
)
def test_update_csr_array_tracks_changes(csr, upd, upd_idx, expected):
    csr.update(upd, upd_idx)
    assert np.all(csr.changed == expected)


class TestTrackedArray:
    def assert_changed(self, arr: TrackedArray, expected_changes):
        assert np.array_equal(arr.changed, expected_changes)

    def assert_diff_equal(self, arr, expected):
        for diff, exp in zip(arr.diff(), expected):
            assert np.array_equal(diff, exp)

    def test_tracked_array_tracks_update(self):
        arr = TrackedArray([3, 3])
        arr[0] = 1
        self.assert_changed(arr, [True, False])

    def test_tracked_array_tracks_update_with_array(self):
        arr = TrackedArray([3, 3])
        arr[:] = [4, 4]
        self.assert_changed(arr, [True, True])

    def test_tracked_array_recognizes_same_value_update(self):
        arr = TrackedArray([3, 3])
        arr[0] = 3
        self.assert_changed(arr, [False, False])

    def test_tracks_multiple_changes(self):
        arr = TrackedArray([3, 3])
        arr[0] = 4
        arr[1] = 4
        self.assert_changed(arr, [True, True])

    def test_resets_values(self):
        arr = TrackedArray([3, 3])
        arr[0] = 4
        arr.reset()
        self.assert_changed(arr, [False, False])

    def test_multidimensional_array(self):
        arr = TrackedArray([[3, 4], [4, 3]])
        arr[arr == 3] = 4
        self.assert_changed(arr, [[True, False], [False, True]])

    def test_changed_floating_points(self):
        arr = TrackedArray([1.0], rtol=1e-2, atol=1e-2)
        arr[0] = 1.001
        self.assert_changed(arr, [False])

    def test_get_diff(self):
        arr = TrackedArray([1, 2, 3])
        arr[0:2] = [3, 3]
        self.assert_diff_equal(arr, (np.array([1, 2]), np.array([3, 3])))

    def test_changes_are_cached(self):
        arr = TrackedArray([1, 2, 3])
        arr[0:2] = [3, 3]
        self.assert_changed(arr, [True, True, False])
        assert np.array_equal(arr._changed, [True, True, False])

    def test_cache_is_updated(self):
        arr = TrackedArray([1, 2, 3])
        arr[0] = 3
        self.assert_changed(arr, [True, False, False])
        arr[1] = 3
        self.assert_changed(arr, [True, True, False])


@pytest.mark.parametrize(
    "a, b, op, expected",
    [
        (
            ensure_csr_data([[1, 2], [3, 4], [5], []]),
            ensure_csr_data([[1, 2], [3, 4], [5], []]),
            operator.add,
            ensure_csr_data([[2, 4], [6, 8], [10], []]),
        ),
        (
            ensure_csr_data([[1, 2], [3, 4], [5], []]),
            2,
            operator.mul,
            ensure_csr_data([[2, 4], [6, 8], [10], []]),
        ),
    ],
)
def test_csr_bin_ops(a, b, op, expected):
    result = op(a, b)
    np.testing.assert_allclose(expected.data, result.data)
    np.testing.assert_allclose(expected.row_ptr, result.row_ptr)
