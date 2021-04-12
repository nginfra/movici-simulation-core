import pytest

from movici_simulation_core.models.traffic_assignment_calculation.model import Model


class TestConfig:
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
    def test_valid_config(self, config, expected_dataset):
        assert Model._get_transport_type(config) == expected_dataset

    @pytest.mark.parametrize(
        "config", [{}, {"roads": []}, {"roads": ["b"], "waterways": ["a"]}, {"roads": ["a", "b"]}]
    )
    def test_invalid_config(self, config):
        with pytest.raises(RuntimeError):
            Model._get_transport_type(config)
