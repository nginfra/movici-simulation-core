import pytest

from movici_data_core.domain_model import ModelType, ScenarioModel


@pytest.mark.parametrize(
    "config, error_message",
    [
        ({"name": "whoops"}, "Prohibited keys in found in ScenarioModel.config: name"),
        ({"type": "whoops"}, "Prohibited keys in found in ScenarioModel.config: type"),
        (
            {"name": "whoops", "type": "whoops"},
            "Prohibited keys in found in ScenarioModel.config: name, type",
        ),
    ],
)
def test_prohibited_scenario_model_keys(config, error_message):
    with pytest.raises(ValueError, match=error_message):
        ScenarioModel("some name", ModelType("sometype"), config=config)
