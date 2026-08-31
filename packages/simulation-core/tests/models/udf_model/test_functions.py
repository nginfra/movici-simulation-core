import numpy as np
import pytest

from movici_simulation_core.core.arrays import TrackedCSRArray
from movici_simulation_core.core.attribute import ensure_csr_data
from movici_simulation_core.core.data_type import UNDEFINED, DataType
from movici_simulation_core.models.udf_model.functions import (
    clip_func,
    default_func,
    divide,
    functions,
    if_func,
    logical_and,
    logical_or,
    max_func,
    min_func,
    modulo,
    power,
    sum_func,
    undefined_on_non_finite,
)


@pytest.mark.parametrize(
    "input_arr, exp",
    [
        (np.array([1, 2, 3]), [1, 2, 3]),
        (np.array([[1], [2], [3]]), [1, 2, 3]),
        (np.array([[1, 1], [2, 2], [3, 3]]), [2, 4, 6]),
        (ensure_csr_data([[1, 2], [3, 4], [5], []]), [3, 7, 5, 0]),
    ],
)
def test_sum(input_arr, exp):
    np.testing.assert_array_equal(sum_func(input_arr), exp)


@pytest.mark.parametrize(
    "inputs, exp",
    [
        ([np.array([1, 2, 3])], [1, 2, 3]),
        ([np.array([[1], [2], [3]])], [1, 2, 3]),
        ([ensure_csr_data([[1, 2], [3, 4], [5], []])], [2, 4, 5, UNDEFINED[int]]),
        ([np.array([1, 2, 3]), np.array([3, 2, 1]), np.array([2, 3, 1])], [3, 3, 3]),
        ([np.array([1, 2, 3]), 2], [2, 2, 3]),
    ],
)
def test_max(inputs, exp):
    np.testing.assert_array_equal(max_func(*inputs), exp)


@pytest.mark.parametrize(
    "input_arr, exp",
    [
        (np.array([1, 2, 3]), [1, 2, 3]),
        (np.array([[1], [2], [3]]), [1, 2, 3]),
        (ensure_csr_data([[1, 2], [3, 4], [5], []]), [1, 3, 5, UNDEFINED[int]]),
        (ensure_csr_data([[1.0, 2], [3, 4], [5], []]), [1.0, 3, 5, UNDEFINED[float]]),
    ],
)
def test_min(input_arr, exp):
    assert np.allclose(min_func(input_arr), exp, equal_nan=True)


@pytest.mark.parametrize(
    "input_arr, default, exp",
    [
        (np.array([1, UNDEFINED[int]]), 0, np.array([1, 0])),
        (np.array([1, UNDEFINED[float]]), 0, np.array([1, 0])),
        (np.array([[1, 2], [UNDEFINED[int], UNDEFINED[int]]]), 0, np.array([[1, 2], [0, 0]])),
        (np.array([1, UNDEFINED[int]]), np.array([2, 3]), np.array([1, 3])),
        (
            np.array([[1, 2], [UNDEFINED[int], UNDEFINED[int]]]),
            np.array([3, 2]),
            np.array([[1, 2], [2, 2]]),
        ),
    ],
)
def test_default_uniform(input_arr, default, exp):
    np.testing.assert_array_equal(default_func(input_arr, default), exp)


@pytest.mark.parametrize(
    "input_arr, default, exp",
    [
        (
            ensure_csr_data([[1, 2], None], data_type=DataType(int, csr=True)),
            0,
            ensure_csr_data([[1, 2], [0]]),
        ),
        (
            ensure_csr_data([[1, 2], None], data_type=DataType(int, csr=True)),
            np.array([2, 3]),
            ensure_csr_data([[1, 2], [3]]),
        ),
        (
            ensure_csr_data([[1, 2], None], data_type=DataType(int, csr=True)),
            ensure_csr_data([None, [1, 2]], data_type=DataType(int, csr=True)),
            ensure_csr_data([[1, 2], [1, 2]]),
        ),
    ],
)
def test_default_csr(input_arr, default, exp):
    result = default_func(input_arr, default)
    np.testing.assert_array_equal(result.data, exp.data)
    np.testing.assert_array_equal(result.row_ptr, exp.row_ptr)


@pytest.mark.parametrize(
    "inputs, exp, dtype",
    [
        ((True, 1, 2.0), 1, int),
        ((False, 1, 2.0), 2.0, float),
        ((np.array([True, False]), 2, 1), [2, 1], int),
        ((np.array([True, False]), np.array([1, 2]), np.array([3, 4])), [1, 4], int),
        ((np.array([True, False]), np.array([1, 2]), 3), [1, 3], int),
        ((np.array([True, False]), np.array([1.0, 2.0]), 3), [1, 3], float),
        ((np.array([True, False]), 3, np.array([1.0, 2.0])), [3, 2], int),
    ],
)
def test_if_func(inputs, exp, dtype):
    result = if_func(*inputs)
    np.testing.assert_array_equal(result, exp)
    if isinstance(result, np.ndarray):
        assert result.dtype == dtype
    else:
        assert isinstance(result, dtype)


@pytest.mark.parametrize(
    "numerator, denominator, expected",
    [
        (np.array([1.0, 3.0]), np.array([2.0, 2.0]), [0.5, 1.5]),
        # a division that cannot produce a finite number yields an undefined value
        (np.array([1.0, 0.0]), np.array([0.0, 0.0]), [np.nan, np.nan]),
        # an undefined operand propagates into the result
        (np.array([UNDEFINED[float], 1.0]), np.array([2.0, 2.0]), [np.nan, 0.5]),
        (np.array([1.0, 2.0]), np.array([UNDEFINED[float], 2.0]), [np.nan, 1.0]),
    ],
)
def test_divide(numerator, denominator, expected):
    np.testing.assert_array_equal(divide(numerator, denominator), expected)


def test_divide_with_csr():
    result = divide(ensure_csr_data([[1.0, 2.0], [3.0], []]), np.array([2.0, 0.0, 1.0]))
    assert isinstance(result, TrackedCSRArray)
    np.testing.assert_array_equal(result.data, [0.5, 1.0, np.nan])


@pytest.mark.parametrize(
    "func, args, expected",
    [
        (power, (np.array([2.0, 3.0]), 2), [4.0, 9.0]),
        (power, (np.array([0.0, 2.0]), -1), [np.nan, 0.5]),
        (modulo, (np.array([7.0, 8.0]), 3), [1.0, 2.0]),
        (modulo, (np.array([7.0, 8.0]), 0), [np.nan, np.nan]),
        (logical_and, (np.array([True, True]), np.array([True, False])), [True, False]),
        (logical_or, (np.array([True, False]), np.array([False, False])), [True, False]),
        (clip_func, (np.array([0.0, 1.5, 3.0]), 1, 2), [1.0, 1.5, 2.0]),
        (
            clip_func,
            (np.array([0.0, 3.0]), np.array([1.0, 1.0]), np.array([2.0, 2.0])),
            [1.0, 2.0],
        ),
    ],
)
def test_operator_functions(func, args, expected):
    np.testing.assert_array_equal(func(*args), expected)


@pytest.mark.parametrize(
    "name, arg, expected",
    [
        ("abs", np.array([-1.0, 2.0]), [1.0, 2.0]),
        ("sqrt", np.array([4.0, 9.0]), [2.0, 3.0]),
        ("exp", np.array([0.0]), [1.0]),
        ("floor", np.array([1.7, -1.2]), [1.0, -2.0]),
        ("ceil", np.array([1.2, -1.7]), [2.0, -1.0]),
        ("round", np.array([1.4, 1.6]), [1.0, 2.0]),
        ("sign", np.array([-2.0, 0.0, 3.0]), [-1.0, 0.0, 1.0]),
        ("not", np.array([True, False]), [False, True]),
        ("log", np.array([1.0]), [0.0]),
        # the logarithm of zero is -inf, which has no representation in a dataset
        ("log", np.array([0.0]), [np.nan]),
        ("log10", np.array([100.0, 0.0]), [2.0, np.nan]),
        ("log2", np.array([8.0, 0.0]), [3.0, np.nan]),
        # an undefined operand propagates into the result
        ("sqrt", np.array([UNDEFINED[float]]), [np.nan]),
    ],
)
def test_elementwise_functions(name, arg, expected):
    np.testing.assert_allclose(functions[name](arg), expected)


@pytest.mark.parametrize("name", ["abs", "sqrt", "floor", "not", "log"])
def test_elementwise_functions_preserve_csr_structure(name):
    arr = ensure_csr_data([[1.0, 4.0], [9.0], []])
    result = functions[name](arr)
    assert isinstance(result, TrackedCSRArray)
    np.testing.assert_array_equal(result.row_ptr, arr.row_ptr)


@pytest.mark.parametrize(
    "value, expected",
    [
        (np.array([1.0, np.inf, -np.inf]), [1.0, np.nan, np.nan]),
        # integers have no non-finite values and are left alone
        (np.array([1, 2]), [1, 2]),
        (np.inf, np.nan),
        (1.0, 1.0),
    ],
)
def test_undefined_on_non_finite(value, expected):
    np.testing.assert_array_equal(undefined_on_non_finite(value), expected)


@pytest.mark.parametrize("func", [min_func, max_func])
def test_extreme_func_accepts_csr_in_any_position(func):
    """a csr operand determines the shape of the result, wherever it appears in the arguments"""
    csr = ensure_csr_data([[10.0, 11.0], [20.0, 22.0]])
    uniform = np.array([15.0, 15.0])

    csr_first = func(csr, uniform)
    uniform_first = func(uniform, csr)

    assert isinstance(uniform_first, TrackedCSRArray)
    np.testing.assert_array_equal(uniform_first.data, csr_first.data)
    np.testing.assert_array_equal(uniform_first.row_ptr, csr_first.row_ptr)
