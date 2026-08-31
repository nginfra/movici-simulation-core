import numpy as np
import pytest

from movici_simulation_core.core.arrays import TrackedCSRArray
from movici_simulation_core.models.common.model_util import get_transport_info, safe_divide


@pytest.mark.parametrize(
    ("config", "expected_modality", "expected_dataset"),
    [
        ({"roads": ["a"]}, "roads", "a"),
        ({"roads": "a"}, "roads", "a"),
        (
            {
                "waterways": ["a"],
            },
            "waterways",
            "a",
        ),
        ({"tracks": ["b"]}, "tracks", "b"),
        ({"roads": ["b"], "waterways": []}, "roads", "b"),
        ({"modality": "tracks", "dataset": ["some_dataset"]}, "tracks", "some_dataset"),
        ({"modality": "tracks", "dataset": "some_dataset"}, "tracks", "some_dataset"),
    ],
)
def test_transport_info_of_valid_transport_config(config, expected_modality, expected_dataset):
    assert get_transport_info(config) == (expected_modality, expected_dataset)


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"roads": []},
        {"roads": ["b"], "waterways": ["a"]},
        {"roads": ["a", "b"]},
        {"roads": ["a"], "modality": "tracks", "dataset": ["a"]},
    ],
)
def test_invalid_transport_config(config):
    with pytest.raises(RuntimeError):
        get_transport_info(config)


@pytest.mark.parametrize(
    "numerator, denominator, fill_value, expected",
    [
        (
            np.array([0.0, 0.0, 1.0, 1.0]),
            np.array([1.0, 0.0, 1.0, 0.0]),
            -1,
            np.array([0, -1, 1, -1]),
        ),
        (2, 1, -1, 2),
        (0, 1, -1, 0),
        (0, 0, -1, -1),
        (1, 0, -1, -1),
        (1, np.array([0, 0]), -1, [-1, -1]),
    ],
)
def test_safe_divide(numerator, denominator, fill_value, expected):
    result = safe_divide(numerator, denominator, fill_value)
    if np.isscalar(expected):
        assert result == expected
    else:
        assert np.array_equal(result, expected)


@pytest.fixture
def csr():
    return TrackedCSRArray(np.array([10.0, 20.0, 30.0, 40.0]), np.array([0, 2, 4]))


@pytest.mark.parametrize(
    "numerator, denominator, fill_value, expected",
    [
        ("csr", np.array([2.0, 4.0]), None, [5.0, 10.0, 7.5, 10.0]),
        ("csr", 10.0, None, [1.0, 2.0, 3.0, 4.0]),
        (40.0, "csr", None, [4.0, 2.0, 40.0 / 30, 1.0]),
        # a division by zero is filled just like it is for uniform arrays
        ("csr", np.array([2.0, 0.0]), -1, [5.0, 10.0, -1.0, -1.0]),
    ],
)
def test_safe_divide_with_csr_array(numerator, denominator, fill_value, csr, expected):
    """np.asarray turns a csr array into an object array, which would silently produce garbage"""
    numerator = csr if numerator == "csr" else numerator
    denominator = csr if isinstance(denominator, str) else denominator

    result = safe_divide(numerator, denominator, fill_value)

    assert isinstance(result, TrackedCSRArray)
    np.testing.assert_allclose(result.data, expected)
    np.testing.assert_array_equal(result.row_ptr, csr.row_ptr)
