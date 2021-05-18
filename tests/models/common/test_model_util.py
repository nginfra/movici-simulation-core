import pytest

from movici_simulation_core.models.common.model_util import get_transport_type


@pytest.mark.parametrize(
    ("config", "expected_dataset"),
    [
        ({"roads": ["a"]}, "roads"),
        (
            {
                "waterways": ["a"],
            },
            "waterways",
        ),
        ({"tracks": ["a"]}, "tracks"),
        ({"roads": ["a"], "waterways": []}, "roads"),
    ],
)
def test_valid_transport_config(config, expected_dataset):
    assert get_transport_type(config) == expected_dataset


@pytest.mark.parametrize(
    "config", [{}, {"roads": []}, {"roads": ["b"], "waterways": ["a"]}, {"roads": ["a", "b"]}]
)
def test_invalid_transport_config(config):
    with pytest.raises(RuntimeError):
        get_transport_type(config)
