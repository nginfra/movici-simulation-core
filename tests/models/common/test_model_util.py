import numpy as np
import pytest

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
            np.array([0, 0, 1, -1]),
        ),
        (2, 1, -1, 2),
        (0, 1, -1, 0),
        (0, 0, -1, 0),
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
