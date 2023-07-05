import numpy as np
import pytest

from movici_simulation_core.core.data_type import UNDEFINED
from movici_simulation_core.csr import (
    csr_binop,
    generate_update,
    isclose,
    row_wise_max,
    row_wise_min,
    row_wise_sum,
    rows_contain,
    rows_equal,
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
        (np.zeros(1000), np.nan, True, np.zeros(1000, dtype=bool)),
        (np.zeros(1000), np.ones(1000), True, np.zeros(1000, dtype=bool)),
        (np.zeros(1000), np.zeros(1000), True, np.ones(1000, dtype=bool)),
        # (np.zeros((1000, 2)), np.zeros((1000, 2)), True, np.ones((1000, 2), dtype=bool)),
        # (np.zeros((1000, 2)), np.ones((1000, 2)), True, np.zeros((1000, 2), dtype=bool)),
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
        (
            np.array([], dtype=int),
            np.array([0], dtype=int),
            np.array([1]),
            True,
            [],
        ),
        (
            np.array([], dtype=int),
            np.array([0, 0], dtype=int),
            np.array([UNDEFINED[int]]),
            True,
            [False],
        ),
        (
            np.array([], dtype=float),
            np.array([0, 0], dtype=int),
            np.array([UNDEFINED[float]]),
            True,
            [False],
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


@pytest.mark.parametrize(
    "data, row_ptr, expected",
    [
        (np.array([1, 2, 3, 4]), np.array([0, 2, 4, 4]), [3, 7, 0]),
        (np.array([1.1, 2]), np.array([0, 2]), [3.1]),
        (np.array([1.1, np.nan]), np.array([0, 1, 2]), [1.1, np.nan]),
    ],
)
def test_row_wise_sum(data, row_ptr, expected):
    np.testing.assert_almost_equal(row_wise_sum(data, row_ptr), expected)


@pytest.mark.parametrize(
    "data, row_ptr, empty_row, expected",
    [
        (np.array([1, 2, 3, 4]), np.array([0, 2, 4]), None, [2, 4]),
        (np.array([2, 1.1]), np.array([0, 2]), None, [2.0]),
        (np.array([1.1, np.nan]), np.array([0, 1, 2]), None, [1.1, np.nan]),
        (np.array([1]), np.array([0, 0, 1]), 0, [0, 1]),
    ],
)
def test_row_wise_max(data, row_ptr, empty_row, expected):
    np.testing.assert_almost_equal(row_wise_max(data, row_ptr, empty_row), expected)


@pytest.mark.parametrize(
    "data, row_ptr, empty_row, expected",
    [
        (np.array([1, 2, 3, 4]), np.array([0, 2, 4]), None, [1, 3]),
        (np.array([2, 1.1]), np.array([0, 2]), None, [1.1]),
        (np.array([1.1, np.nan]), np.array([0, 1, 2]), None, [1.1, np.nan]),
        (np.array([1]), np.array([0, 0, 1]), 0, [0, 1]),
    ],
)
def test_row_wise_min(data, row_ptr, empty_row, expected):
    np.testing.assert_almost_equal(row_wise_min(data, row_ptr, empty_row), expected)


@pytest.mark.parametrize("func", [row_wise_max, row_wise_min])
def test_row_wise_func_empty_row_raises(func):
    with pytest.raises(ValueError):
        func(np.array([]), np.array([0, 0]))


@pytest.mark.parametrize("func", [row_wise_max, row_wise_min])
def test_unsupported_dtype_raises(func):
    with pytest.raises(TypeError) as e:
        func(np.array(["a"]), np.array([0, 1]))
    assert str(e.value) == "Only numeric arrays are supported"


@pytest.mark.parametrize(
    "   data,       row_ptr,      mask,      changed,   exp_data, exp_row_ptr",
    [
        ([0, 1, 2], [0, 1, 2, 3], [0, 1, 1], [0, 0, 1], [-1, 2], [0, 1, 2]),
        ([0, 1, 2], [0, 1, 2, 3], [1, 0, 1], [0, 0, 1], [-1, 2], [0, 1, 2]),
        ([0, 1, 2], [0, 1, 2, 3], [1, 0, 1], [0, 0, 0], [-1, -1], [0, 1, 2]),
        ([0, 1, 2], [0, 1, 2, 3], [1, 1, 0], [1, 1, 0], [0, 1], [0, 1, 2]),
        ([0, 1, 2], [0, 1, 3], [0, 1], [0, 1], [1, 2], [0, 2]),
        ([], [0, 0, 0], [1, 1], [1, 0], [-1], [0, 0, 1]),
        ([], [0, 0, 0], [1, 1], [0, 1], [-1], [0, 1, 1]),
        ([], [0, 0], [0], [0], [], [0]),
        ([], [0, 0], [1], [0], [-1], [0, 1]),
        ([], [0, 0], [1], [1], [], [0, 0]),
        ([1], [0, 0, 1], [1, 1], [0, 1], [-1, 1], [0, 1, 2]),
        ([1], [0, 0, 1], [1, 1], [1, 0], [-1], [0, 0, 1]),
        ([0, 1, 2, 3, 4, 5, 6], [0, 2, 4, 7], [0, 1, 1], [0, 0, 1], [-1, 4, 5, 6], [0, 1, 4]),
        ([0, 1, 2, 3, 4, 5, 6], [0, 2, 4, 7], [1, 0, 1], [0, 0, 1], [-1, 4, 5, 6], [0, 1, 4]),
        ([0, 1, 2, 3, 4], [0, 2, 4, 5], [1, 1, 1], [1, 0, 1], [0, 1, -1, 4], [0, 2, 3, 4]),
        ([[0, 1], [2, 3]], [0, 1, 2], [1, 1], [1, 0], [[0, 1], [-1, -1]], [0, 1, 2]),
    ],
)
def test_generate_update(data, row_ptr, mask, changed, exp_data, exp_row_ptr):
    res_data, res_row_ptr = generate_update(
        np.asarray(data, dtype=int),
        np.asarray(row_ptr, dtype=int),
        np.asarray(mask, dtype=bool),
        np.asarray(changed, dtype=bool),
        undefined=-1,
    )
    assert np.array_equal(res_data, exp_data)
    assert np.array_equal(res_row_ptr, exp_row_ptr)


@pytest.mark.parametrize(
    "   data,       row_ptr,      mask,      changed,   exp_data, exp_row_ptr",
    [
        (["bla"], [0, 1], [1], [0], ["_udf_"], [0, 1]),
        ([], [0, 1], [1], [0], ["_udf_"], [0, 1]),
        (["bla"], [0, 1], [1], [1], ["bla"], [0, 1]),
        (["bla", "bli"], [0, 2], [1], [1], ["bla", "bli"], [0, 2]),
        ([["bla", "bli"]], [0, 1], [1], [1], [["bla", "bli"]], [0, 1]),
    ],
)
def test_generate_update_unicode(data, row_ptr, mask, changed, exp_data, exp_row_ptr):
    res_data, res_row_ptr = generate_update(
        np.asarray(data, dtype="<U8"),
        np.asarray(row_ptr, dtype=int),
        np.asarray(mask, dtype=bool),
        np.asarray(changed, dtype=bool),
        undefined="_udf_",
    )
    assert np.array_equal(res_data, exp_data)
    assert np.array_equal(res_row_ptr, exp_row_ptr)


@pytest.mark.parametrize(
    "operator, expected",
    [
        (np.add, [2, 4, 6]),
        (np.subtract, [0, 0, 2]),
        (np.multiply, [1, 4, 8]),
        (np.divide, [1, 1, 2]),
        (np.minimum, [1, 2, 2]),
        (np.equal, [True, True, False]),
    ],
)
def test_csr_binop(operator, expected):
    # csr array in form [[1], [2,4], []]
    data = np.array([1, 2, 4], dtype=int)
    row_ptr = np.array([0, 1, 3, 3])
    operand = np.array([1, 2, 3])
    np.testing.assert_array_equal(csr_binop(data, row_ptr, operand, operator), expected)
