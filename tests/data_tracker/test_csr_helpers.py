import numpy as np
import pytest

from movici_simulation_core.data_tracker.csr_helpers import (
    isclose,
    rows_equal,
    rows_contain,
    rows_intersect,
)


@pytest.mark.parametrize(
    ["arr", "val", "equal_nan", "expected"],
    [
        (np.array([1.0, np.nan]), np.nan, True, [False, True]),
        (np.array([1.0, np.nan]), np.nan, False, [False, False]),
        (np.array([1.0, 2.0]), 1.0, False, [True, False]),
        (np.array([1.0, 2.0]), 1, False, [True, False]),
        (np.array([1, 2]), 1, False, [True, False]),
        (np.array([1, 2]), np.array([1, 1]), False, [True, False]),
        (np.array([[1, 2]]), 1, False, [[True, False]]),
        (np.array(["a", "b"]), "a", False, [True, False]),
        (np.array([["a"], ["b"]]), "a", False, [[True], [False]]),
        (np.array(["aa", "bb"]), "aaa", False, [False, False]),
        (np.array(["a", "b"], dtype="<U3"), "a", False, [True, False]),
    ],
)
def test_is_close(arr, val, equal_nan, expected):
    assert np.array_equal(isclose(arr, val, equal_nan=equal_nan), expected)
    assert np.array_equal(isclose(val, arr, equal_nan=equal_nan), expected)


@pytest.mark.parametrize(
    ["data", "row_ptr", "row", "equal_nan", "expected"],
    [
        (
            np.array([1.0, 2.0, 3.0]),
            np.array([0, 2, 3]),
            np.array([1.0, 2.0]),
            False,
            [True, False],
        ),
        (
            np.array(["a", "b", "c"]),
            np.array([0, 2, 3]),
            np.array(["a", "b"]),
            False,
            [True, False],
        ),
        (
            np.array([1.0, np.nan, np.nan]),
            np.array([0, 2, 3]),
            np.array([np.nan]),
            True,
            [False, True],
        ),
    ],
)
def test_rows_equal(data, row_ptr, row, equal_nan, expected):
    assert np.array_equal(rows_equal(data, row_ptr, row, equal_nan=equal_nan), expected)


@pytest.mark.parametrize(
    ["data", "row_ptr", "val", "equal_nan", "expected"],
    [
        (np.array([1, 2, 3]), np.array([0, 2, 3]), 1, False, [True, False]),
        (np.array([1, np.nan, 3]), np.array([0, 2, 3]), np.nan, False, [False, False]),
        (np.array([1, np.nan, 3]), np.array([0, 2, 3]), np.nan, True, [True, False]),
        (np.array(["a", "b", "c"]), np.array([0, 2, 3]), "a", False, [True, False]),
    ],
)
def test_rows_contain(data, row_ptr, val, equal_nan, expected):
    assert np.array_equal(rows_contain(data, row_ptr, val, equal_nan=equal_nan), expected)


@pytest.mark.parametrize(
    ["data", "row_ptr", "row", "equal_nan", "expected"],
    [
        (
            np.array([1.0, 2.0, 3.0]),
            np.array([0, 2, 3]),
            np.array([1.0, 3.0]),
            False,
            [True, True],
        ),
        (
            np.array(["a", "b", "c"]),
            np.array([0, 2, 3]),
            np.array(["a"]),
            False,
            [True, False],
        ),
        (
            np.array([1.0, np.nan, np.nan]),
            np.array([0, 2, 3]),
            np.array([np.nan]),
            True,
            [True, True],
        ),
    ],
)
def test_rows_intersect(data, row_ptr, row, equal_nan, expected):
    assert np.array_equal(rows_intersect(data, row_ptr, row, equal_nan=equal_nan), expected)
