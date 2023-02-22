import json

import numpy as np
import pytest
from jsonschema import ValidationError

from movici_simulation_core.core.arrays import TrackedCSRArray
from movici_simulation_core.models.evacuation_point_resolution import (
    MODEL_CONFIG_SCHEMA_PATH,
    EvacuatonPointResolution,
)
from movici_simulation_core.validate import validate_and_process


@pytest.fixture
def model_config():
    return {
        "dataset": "road_dataset",
        "evacuation_points": {"entity_group": "evacuation_point_entities", "attribute": "id"},
        "road_segments": {
            "entity_group": "road_segment_entities",
            "attribute": "evacuation.label",
        },
    }


@pytest.fixture
def dataset():
    return {
        "name": "road_dataset",
        "data": {
            "road_segment_entities": {
                "id": [1, 2, 3, 4, 5, 6],
            },
            "evacuation_point_entities": {
                "id": [4, 5],
                "evacuation.road_ids": [[1, 2], [3]],
                "label": [2, 3],
            },
        },
    }


@pytest.fixture
def init_data(dataset):
    return [(dataset["name"], dataset)]


@pytest.fixture
def tester(create_model_tester, model_config):
    return create_model_tester(
        EvacuatonPointResolution, model_config, raise_on_premature_shutdown=False
    )


def test_create_mapping(model_config):
    model = EvacuatonPointResolution(model_config)
    road_ids = TrackedCSRArray([1, 2, 3], [0, 2, 3])
    labels = np.array([10, 20])
    model.create_label_mapping(road_ids, labels)
    assert model.label_mapping == {
        1: 10,
        2: 10,
        3: 20,
    }


@pytest.mark.parametrize(
    "attribute, expected",
    [
        ("label", [2, 2, 3, 2, 2, 3]),
        ("id", [4, 4, 5, 4, 4, 5]),
    ],
)
def test_calculate_in_different_mode(attribute, expected, create_model_tester, model_config):
    model_config["evacuation_points"]["attribute"] = attribute
    tester = create_model_tester(
        EvacuatonPointResolution, model_config, raise_on_premature_shutdown=False
    )
    tester.initialize()
    result, _ = tester.update(
        0,
        {
            "road_dataset": {
                "road_segment_entities": {
                    "id": [1, 2, 3, 4, 5, 6],
                    "evacuation.last_id": [1, 2, 3, 1, 2, 3],
                }
            }
        },
    )
    labels = result["road_dataset"]["road_segment_entities"]["evacuation.label"]
    assert labels == expected


def test_with_road_ids_in_initial_data(dataset, create_model_tester, model_config):
    dataset["data"]["road_segment_entities"]["evacuation.last_id"] = [1, 2, 3, 1, 2, 3]
    tester = create_model_tester(
        EvacuatonPointResolution, model_config, raise_on_premature_shutdown=False
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    labels = result["road_dataset"]["road_segment_entities"]["evacuation.label"]
    assert labels == [4, 4, 5, 4, 4, 5]


def test_multiple_updates(create_model_tester, model_config):
    tester = create_model_tester(
        EvacuatonPointResolution, model_config, raise_on_premature_shutdown=False
    )
    tester.initialize()
    tester.update(
        0,
        {
            "road_dataset": {
                "road_segment_entities": {
                    "id": [1, 2, 3, 4, 5, 6],
                    "evacuation.last_id": [1, 2, 3, 1, 2, 3],
                }
            }
        },
    )
    result, _ = tester.update(
        0,
        {
            "road_dataset": {
                "road_segment_entities": {
                    "id": [5, 6],
                    "evacuation.last_id": [3, 2],
                }
            }
        },
    )
    labels = result["road_dataset"]["road_segment_entities"]["evacuation.label"]
    ids = result["road_dataset"]["road_segment_entities"]["id"]
    assert ids == [5, 6]
    assert labels == [5, 4]


@pytest.mark.parametrize(
    "config",
    [
        {
            "dataset": "some_dataset",
            "evacuation_points": {"entity_group": "some_entities", "attribute": "id"},
            "road_segments": {"entity_group": "some_roads", "attribute": "evacuation.label"},
        },
        {
            "dataset": "some_dataset",
        },
        {
            "dataset": "some_dataset",
            "evacuation_points": {"entity_group": "some_entities", "attribute": "id"},
        },
    ],
)
def test_model_config_schema(config):
    schema = json.loads(MODEL_CONFIG_SCHEMA_PATH.read_text())
    assert validate_and_process(config, schema)


@pytest.mark.parametrize(
    "config",
    [
        {},
        {
            "dataset": "some_dataset",
            "evacuation_points": {"entity_group": "some_entities"},
            "road_segments": {"entity_group": "some_roads", "attribute": "evacuation.label"},
        },
    ],
)
def test_invalid_model_config_schema(config):
    schema = json.loads(MODEL_CONFIG_SCHEMA_PATH.read_text())
    with pytest.raises(ValidationError):
        validate_and_process(config, schema)
