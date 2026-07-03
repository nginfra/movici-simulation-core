import pytest

from movici_data_core.domain_model import DatasetType, ModelType, ScenarioDataset, ScenarioModel
from movici_data_core.exceptions import MoviciValidationError
from movici_data_core.validators import ModelConfigValidator
from movici_simulation_core.validate import MoviciDataRefInfo


@pytest.fixture
def scenario_datasets():
    return [
        ScenarioDataset("some_dataset", DatasetType("some_type")),
        ScenarioDataset("another_dataset", DatasetType("another_type")),
    ]


@pytest.fixture
async def validator(default_model_types, scenario_datasets, get_model_config_validator):
    return (await get_model_config_validator()).for_scenario(
        scenario_datasets, default_model_types
    )


def test_scenario_model_validator(validator: ModelConfigValidator, default_model_types):
    scenario_models = [
        ScenarioModel(
            name="model1",
            type=ModelType("model_a"),
            config={
                "dataset": "some_dataset",
                "entity_group": "transport_nodes",
                "attribute": "id",
            },
        ),
        ScenarioModel(
            name="model2",
            type=ModelType("model_b"),
            config={
                "field": "some_string",
            },
        ),
    ]
    model_1, model_2 = validator.process_model_configs(scenario_models)
    assert model_1 == ScenarioModel(
        name="model1",
        type=default_model_types[0],
        config=scenario_models[0].config,
        references=[
            MoviciDataRefInfo(("dataset",), "some_dataset", movici_type="dataset"),
            MoviciDataRefInfo(("entity_group",), "transport_nodes", movici_type="entityGroup"),
            MoviciDataRefInfo(("attribute",), "id", movici_type="attribute"),
        ],
    )
    assert model_2 == ScenarioModel(
        name="model2",
        type=default_model_types[1],
        config=scenario_models[1].config,
        references=[],
    )


@pytest.mark.parametrize(
    "config, path",
    [
        (ScenarioModel(name="model", type=ModelType("invalid")), "0.type"),
        (ScenarioModel(name="model", type=ModelType("model_b"), config={"field": 123}), "0.field"),
    ],
)
def test_raises_on_invalid_config(config, path, validator):
    with pytest.raises(MoviciValidationError) as e:
        validator.process_model_configs([config])
    error_path = list(e.value.iter_messages())[0][0]
    assert error_path == path
