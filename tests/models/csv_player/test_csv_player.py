from pathlib import Path
import json
import typing as t

from movici_simulation_core.models.csv_player import MODEL_CONFIG_SCHEMA_PATH
from movici_simulation_core.models.csv_player.csv_player import CSVPlayer
from movici_simulation_core.testing.helpers import assert_dataset_dicts_equal
from movici_simulation_core.testing.model_schema import model_config_validator
from movici_simulation_core.testing.model_tester import ModelTester
import pytest


@pytest.fixture
def csv_tape_name():
    return "some_csv_tape"


@pytest.fixture
def csv_tape():
    return "\n".join(
        ",".join(str(i) for i in inner_list)
        for inner_list in [
            ["seconds", "param1", "param2"],
            [0, 10, 100],
            [1, 11, 101],
        ]
    )


@pytest.fixture
def dataset_name():
    return "some_dataset"


@pytest.fixture
def some_dataset():
    return {
        "name": "some_dataset",
        "data": {
            "some_entities": {"id": [1, 2, 3]},
        },
    }


@pytest.fixture
def legacy_model_config(csv_tape_name, dataset_name):
    return {
        "entity_group": [[dataset_name, "some_entities"]],
        "csv_tape": [csv_tape_name],
        "csv_parameters": ["param1", "param2"],
        "target_attributes": [[None, "target1"], [None, "target2"]],
    }


@pytest.fixture
def model_config(csv_tape_name, dataset_name):
    return {
        "entity_group": [dataset_name, "some_entities"],
        "csv_tape": csv_tape_name,
        "csv_parameters": [
            {"parameter": "param1", "target_attribute": "target1"},
            {"parameter": "param2", "target_attribute": "target2"},
        ],
    }


@pytest.fixture
def init_data(tmp_path: Path, csv_tape_name, csv_tape, dataset_name, some_dataset):
    path = tmp_path.joinpath(csv_tape_name).with_suffix(".csv")
    path.write_text(csv_tape)
    return [(csv_tape_name, path), (dataset_name, some_dataset)]


@pytest.fixture
def tester(create_model_tester, model_config):
    return create_model_tester(
        model_type=CSVPlayer, config=model_config, raise_on_premature_shutdown=False
    )


def test_csv_player_datamask(tester: ModelTester, dataset_name):
    datamask = tester.initialize()

    def setify(dm):
        for k, v in dm.items():
            if isinstance(v, t.Sequence):
                dm[k] = set(v)
            else:
                setify(v)
        return datamask

    assert setify(datamask) == {
        "pub": {
            dataset_name: {
                "some_entities": {
                    "target1",
                    "target2",
                }
            },
        },
        "sub": {},
    }


def test_csv_player_update_0(tester: ModelTester, dataset_name):
    tester.initialize()
    result, next_time = tester.update(0, data=None)
    assert next_time == 1
    assert_dataset_dicts_equal(
        result,
        {
            dataset_name: {
                "some_entities": {
                    "id": [1, 2, 3],
                    "target1": [10, 10, 10],
                    "target2": [100, 100, 100],
                }
            }
        },
    )


def test_csv_player_update_1(tester: ModelTester, dataset_name):
    tester.initialize()
    tester.update(0, data=None)
    result, next_time = tester.update(1, data=None)
    assert next_time is None
    assert_dataset_dicts_equal(
        result,
        {
            dataset_name: {
                "some_entities": {
                    "id": [1, 2, 3],
                    "target1": [11, 11, 11],
                    "target2": [101, 101, 101],
                }
            }
        },
    )


def test_model_config_schema(model_config):
    schema = json.loads(MODEL_CONFIG_SCHEMA_PATH.read_text())
    assert model_config_validator(schema)(model_config)


def test_convert_legacy_model_config(legacy_model_config, model_config):
    assert CSVPlayer(legacy_model_config).config == model_config
