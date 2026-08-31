import pytest

from movici_data_core.domain_model import DatasetType, ModelType, ScenarioDataset, ScenarioModel
from movici_data_core.exceptions import MoviciValidationError
from movici_data_core.serialization import dump_dict
from movici_data_core.validators import ModelConfigValidator, ValidatingDatasetSerializer
from movici_simulation_core import AttributeSchema, AttributeSpec, DataType, EntityInitDataFormat
from movici_simulation_core.testing import (
    assert_dataset_dicts_equal,
    dataset_data_to_numpy,
)
from movici_simulation_core.types import FileType
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


class TestValidatingDatasetSerializer:
    @pytest.fixture
    def dataset_data(self):
        return {
            "some_entities": {
                "id": [1, 2, 3],
                "attr": [10.0, 20.0, 30.0],
            },
            "more_entities": {
                "id": [5, 6, 7],
                "csr_attr": [[[1, 3]], [], [[4, 5], [6, 7]]],
            },
        }

    @pytest.fixture
    def serializer(self):
        return ValidatingDatasetSerializer(
            EntityInitDataFormat(
                AttributeSchema(
                    [
                        AttributeSpec("id", DataType(int)),
                        AttributeSpec("attr", DataType(float)),
                        AttributeSpec("csr_attr", DataType(int, (2,), csr=True)),
                    ]
                )
            )
        )

    @staticmethod
    def _serialize_and_validate(dataset_data, serializer):
        serialized = dump_dict({"data": dataset_data}, FileType.JSON)
        result = serializer.loads(serialized, FileType.JSON)
        return result["data"]

    def test_succeeds_valid_dataset_data(self, dataset_data, serializer):
        result = self._serialize_and_validate(dataset_data, serializer)
        assert_dataset_dicts_equal(
            result,
            dataset_data_to_numpy(
                {
                    "some_entities": {
                        "id": [1, 2, 3],
                        "attr": [10.0, 20.0, 30.0],
                    },
                    "more_entities": {
                        "id": [5, 6, 7],
                        "csr_attr": {
                            "data": [[1, 3], [4, 5], [6, 7]],
                            "indptr": [0, 1, 1, 3],
                        },
                    },
                }
            ),
        )

    @pytest.mark.parametrize(
        "dataset_data, error_messages",
        [
            (
                {"some_entities": [1, 2, 3]},
                [("", "Entity group data must be dict")],
            ),
            (
                {"some_entities": {"attr": [1, 2, 3]}},
                [("data.some_entities", "Entity group has no 'id' attribute")],
            ),
            (
                {"some_entities": {"id": [-1, -2, 3]}},
                [("data.some_entities.id", "Negative ids found")],
            ),
            (
                {"some_entities": {"id": [1, 2, 3], "attr": [1, 2, 3, 4]}},
                [("data.some_entities.attr", "Invalid attribute length, expected 3, got 4")],
            ),
            (
                {
                    "some_entities": {
                        "id": [1, 2, 3],
                        "csr_attr": [[[1, 3]], [[4, 5], [6, 7]]],
                    }
                },
                [("data.some_entities.csr_attr", "Invalid attribute length, expected 3, got 2")],
            ),
            (
                {"some_entities": {"id": [1, 2, 3], "attr": [1, 2, 3, 4]}},
                [("data.some_entities.attr", "Invalid attribute length, expected 3, got 4")],
            ),
            (
                {"some_entities": {"id": [1, 2, 3]}, "more_entities": {"id": [2, 3]}},
                [("data.more_entities.id", "Duplicate entries detected: 2, 3")],
            ),
            (
                {
                    "some_entities": {"id": [-1, -2, 3], "attr": [1, 2, 3, 4]},
                    "more_entities": {"id": [4, 4, 5]},
                },
                [
                    ("data.some_entities.id", "Negative ids found"),
                    ("data.some_entities.attr", "Invalid attribute length, expected 3, got 4"),
                    ("data.more_entities.id", "Duplicate entries detected: 4"),
                ],
            ),
        ],
    )
    def test_raises_validation_errors(self, dataset_data, error_messages, serializer):
        with pytest.raises(MoviciValidationError) as e:
            self._serialize_and_validate(dataset_data, serializer)
        assert list(e.value.iter_messages()) == error_messages

    def test_raises_validation_error_on_dataset_data_by_name(self, serializer):

        serialized = dump_dict(
            {"name": "my_dataset", "my_dataset": {"some_entities": {"id": [-1]}}}, FileType.JSON
        )
        with pytest.raises(MoviciValidationError) as e:
            serializer.loads(serialized, FileType.JSON)
        assert list(e.value.iter_messages()) == [
            ("my_dataset.some_entities.id", "Negative ids found")
        ]
