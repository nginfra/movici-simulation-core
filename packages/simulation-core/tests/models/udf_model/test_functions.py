import numpy as np
import pytest

from movici_simulation_core.core.arrays import TrackedCSRArray
from movici_simulation_core.core.attribute import ensure_csr_data
from movici_simulation_core.core.data_type import UNDEFINED, DataType
from movici_simulation_core.models.udf_model.functions import (
    clip_func,
    default_func,
    defined_values,
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
        # both branches determine the result type, also when the condition selects only one
        ((True, 1, 2.0), 1, float),
        ((False, 1, 2.0), 2.0, float),
        ((np.array([True, False]), 2, 1), [2, 1], int),
        ((np.array([True, False]), np.array([1, 2]), np.array([3, 4])), [1, 4], int),
        ((np.array([True, False]), np.array([1, 2]), 3), [1, 3], int),
        ((np.array([True, False]), np.array([1.0, 2.0]), 3), [1, 3], float),
        ((np.array([True, False]), 3, np.array([1.0, 2.0])), [3, 2], float),
        ((np.array([True, False]), True, False), [True, False], bool),
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


@pytest.mark.parametrize(
    "lower, upper, expected",
    [
        # np.clip cannot broadcast a per entity bound along the rows of a csr array
        (2.0, 3.0, [2.0, 2.0, 3.0]),
        # rows [1.0, 2.0] and [4.0] get their own bounds: [2.0, 3.0] and [0.0, 3.5]
        (np.array([2.0, 0.0]), np.array([3.0, 3.5]), [2.0, 2.0, 3.5]),
    ],
)
def test_clip_a_csr_array(lower, upper, expected):
    csr = TrackedCSRArray(np.array([1.0, 2.0, 4.0]), np.array([0, 2, 3]))
    result = clip_func(csr, lower, upper)
    assert isinstance(result, TrackedCSRArray)
    np.testing.assert_array_equal(result.data, expected)


def test_undefined_on_non_finite_does_not_modify_a_csr_argument():
    csr = TrackedCSRArray(np.array([1.0, np.inf]), np.array([0, 2]))

    result = undefined_on_non_finite(csr)

    np.testing.assert_array_equal(csr.data, [1.0, np.inf])
    np.testing.assert_array_equal(result.data, [1.0, np.nan])


def test_exp_that_overflows_yields_an_undefined_value():
    """an overflow has no representation in a dataset any more than a division by zero does"""
    np.testing.assert_array_equal(functions["exp"](np.array([1.0, 1e9])), [np.e, np.nan])


@pytest.mark.parametrize(
    "func, value, expected",
    [
        # a csr array with a unit shape reduces over both its rows and its unit shape
        (sum_func, [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], [10.0, 11.0]),
        (min_func, [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], [1.0, 5.0]),
        (max_func, [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], [4.0, 6.0]),
    ],
)
def test_reducing_a_csr_array_with_a_unit_shape(func, value, expected):
    csr = TrackedCSRArray(np.array(value), np.array([0, 2, 3]))
    np.testing.assert_array_equal(func(csr), expected)


@pytest.mark.parametrize(
    "func, args, expected",
    [
        # with several arguments the extremes are elementwise, and a csr argument decides the
        # shape of the result wherever it appears
        (min_func, ("csr", np.array([2.0, 2.0])), [1.0, 2.0, 2.0]),
        (min_func, (np.array([2.0, 2.0]), "csr"), [1.0, 2.0, 2.0]),
        (min_func, ("csr", 2.0), [1.0, 2.0, 2.0]),
        (max_func, ("csr", np.array([2.0, 2.0])), [2.0, 2.0, 3.0]),
        (max_func, (np.array([2.0, 2.0]), "csr"), [2.0, 2.0, 3.0]),
    ],
)
def test_extreme_functions_over_mixed_shapes(func, args, expected):
    csr = TrackedCSRArray(np.array([1.0, 2.0, 3.0]), np.array([0, 2, 3]))
    result = func(*(csr if isinstance(arg, str) else arg for arg in args))
    assert isinstance(result, TrackedCSRArray)
    np.testing.assert_array_equal(result.data, expected)


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


@pytest.mark.parametrize(
    "value, expected",
    [
        (np.array([1.0, 2.0, 3.0]), [1.0, 2.0, 3.0]),
        # undefined values are left out, so that one undefined entity does not poison the group
        (np.array([1.0, UNDEFINED[float], 3.0]), [1.0, 3.0]),
        (np.array([1, UNDEFINED[int], 3], dtype="<i4"), [1, 3]),
        (ensure_csr_data([[1.0, 2.0], [3.0], []]), [1.0, 2.0, 3.0]),
        # a multidimensional attribute is flattened
        (np.array([[1.0, 2.0], [3.0, 4.0]]), [1.0, 2.0, 3.0, 4.0]),
        (np.array([], dtype=float), []),
        (2.0, [2.0]),
    ],
)
def test_defined_values(value, expected):
    np.testing.assert_array_equal(defined_values(value), expected)


@pytest.mark.parametrize(
    "name, value, expected",
    [
        ("total", np.array([1.0, 2.0, 3.0]), 6.0),
        ("total", np.array([1.0, UNDEFINED[float], 3.0]), 4.0),
        ("total", ensure_csr_data([[1.0, 2.0], [3.0], []]), 6.0),
        ("total", np.array([], dtype=float), 0.0),
        ("mean", np.array([1.0, 2.0, 3.0]), 2.0),
        ("mean", np.array([1.0, UNDEFINED[float], 3.0]), 2.0),
        ("count", np.array([1.0, 2.0, 3.0]), 3),
        ("count", np.array([1.0, UNDEFINED[float], 3.0]), 2),
        ("count", np.array([], dtype=float), 0),
        ("any", np.array([False, True]), True),
        ("any", np.array([False, False]), False),
        ("any", np.array([], dtype=bool), False),
        ("all", np.array([True, True]), True),
        ("all", np.array([True, False]), False),
        ("all", np.array([], dtype=bool), True),
    ],
)
def test_group_reducers(name, value, expected):
    assert functions[name](value) == expected


@pytest.mark.parametrize(
    "name, expected",
    [
        # a scalar is an entity group of one, and an undefined scalar one of none
        ("total", 2.0),
        ("mean", 2.0),
        ("count", 1),
        ("any", True),
        ("all", True),
    ],
)
def test_group_reducers_of_a_scalar(name, expected):
    assert functions[name](2.0) == expected


@pytest.mark.parametrize(
    "name, expected",
    [
        ("total", 0.0),
        ("count", 0),
        ("any", False),
        # nothing in an empty group is false, so everything in it is true
        ("all", True),
    ],
)
def test_group_reducers_of_an_undefined_scalar(name, expected):
    assert functions[name](UNDEFINED[float]) == expected


def test_mean_of_an_undefined_scalar_is_undefined():
    assert np.isnan(functions["mean"](UNDEFINED[float]))


def test_if_does_not_truncate_the_branch_it_does_not_take_its_type_from():
    """taking the result type from the first branch alone silently truncated the second"""
    result = if_func(np.array([True, False]), np.array([1, 2]), np.array([1.5, 2.5]))
    np.testing.assert_array_equal(result, [1.0, 2.5])


def test_sum_of_a_boolean_csr_attribute_counts():
    """the row wise sum is calculated in the dtype of the data, which cannot hold a count"""
    result = sum_func(ensure_csr_data([[True, True, True], [True], []]))
    np.testing.assert_array_equal(result, [3, 1, 0])


def test_mean_of_an_entity_group_without_defined_values_is_undefined():
    assert np.isnan(functions["mean"](np.array([UNDEFINED[float]])))
