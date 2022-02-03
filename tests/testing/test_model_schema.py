import jsonschema
import pytest

from movici_simulation_core.testing.model_schema import model_config_validator

model_schemas = {
    "empty": {
        "name": "some_model",
        "schema": {},
    },
    "single_dataset_category": {
        "name": "some_model",
        "schema": {},
        "dataset_categories": [{"name": "datasets", "type": "mv_network", "required": True}],
    },
    "single_entity_category": {
        "name": "some_model",
        "schema": {},
        "entity_categories": [{"name": "entities", "required": True, "require_one": True}],
    },
    "strict_validation": {"name": "some_model", "schema": {}, "strict_validation": True},
    "strict_validation_with_category": {
        "name": "some_model",
        "schema": {},
        "dataset_categories": [{"name": "datasets", "type": "mv_network", "required": True}],
        "strict_validation": True,
    },
}


@pytest.mark.parametrize(
    "model_schema, config",
    [
        (model_schemas["single_dataset_category"], {"datasets": ["dataset", "dataset2"]}),
        (model_schemas["single_entity_category"], {"entities": [["dataset", "entity_group"]]}),
        (model_schemas["empty"], {"additional": "entry"}),
        (model_schemas["strict_validation"], {"type": "some_model", "name": "model_name"}),
        (
            model_schemas["strict_validation_with_category"],
            {"type": "some_model", "name": "model_name", "datasets": ["dataset", "dataset2"]},
        ),
    ],
)
def test_can_validate(model_schema, config):
    validator = model_config_validator(model_schema)
    assert validator(config)


@pytest.mark.parametrize(
    "model_schema, config",
    [
        (model_schemas["strict_validation"], {"additional": "entry"}),
        (model_schemas["strict_validation"], {"type": "wrong_type"}),
    ],
)
def test_raises_errors(model_schema, config):
    validator = model_config_validator(model_schema)

    with pytest.raises(jsonschema.ValidationError):
        validator(config)
