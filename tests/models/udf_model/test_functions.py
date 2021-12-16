import numpy as np
import pytest

from movici_simulation_core.core.schema import UNDEFINED, DataType
from movici_simulation_core.data_tracker.attribute import ensure_csr_data
from movici_simulation_core.models.udf_model.functions import (
    sum_func,
    max_func,
    min_func,
    default_func,
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
    "input_arr, exp",
    [
        (np.array([1, 2, 3]), [1, 2, 3]),
        (np.array([[1], [2], [3]]), [1, 2, 3]),
        (ensure_csr_data([[1, 2], [3, 4], [5], []]), [2, 4, 5, UNDEFINED[int]]),
    ],
)
def test_max(input_arr, exp):
    np.testing.assert_array_equal(max_func(input_arr), exp)


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
    ],
)
def test_default_csr(input_arr, default, exp):
    result = default_func(input_arr, default)
    np.testing.assert_array_equal(result.data, exp.data)
    np.testing.assert_array_equal(result.row_ptr, exp.row_ptr)
