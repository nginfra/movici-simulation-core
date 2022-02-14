import pytest

from movici_simulation_core.core.schema import AttributeSpec
from movici_simulation_core.models.tape_player.model import Model
from movici_simulation_core.testing.helpers import data_mask_compare
from movici_simulation_core.testing.model_tester import ModelTester


@pytest.fixture
def target_dataset():
    return "dataset"


@pytest.fixture()
def tape_dataset_name():
    return "tapefile"


@pytest.fixture
def init_data(target_dataset):
    return {target_dataset: {"entity_group": {"id": [0]}}}


@pytest.fixture
def update_1():
    return {"entity_group": {"id": [0], "attribute": [10]}}


@pytest.fixture
def update_2():
    return {"entity_group": {"id": [0], "attribute": [20]}}


@pytest.fixture
def tape_data(target_dataset, update_1, update_2):
    return {
        "tabular_data_name": target_dataset,
        "time_series": [1, 2],
        "data_series": [update_1, update_2],
    }


@pytest.fixture
def more_tape_data(target_dataset):
    return {
        "data": {
            "tabular_data_name": target_dataset,
            "time_series": [1],
            "data_series": [{"entity_group": {"id": [0], "another_attribute": [11]}}],
        }
    }


@pytest.fixture
def tape_dataset(tape_data, tape_dataset_name):
    return {"name": tape_dataset_name, "type": "tabular", "data": tape_data}


@pytest.fixture
def model(tape_dataset_name):
    return Model({"tabular": [tape_dataset_name]})


@pytest.fixture
def additional_attributes():
    from movici_simulation_core.core import DataType

    return [
        AttributeSpec("attribute", DataType(int, (), False)),
        AttributeSpec("another_attribute", DataType(int, (), False)),
    ]


@pytest.fixture
def model_tester(
    model, target_dataset, tape_dataset_name, tape_dataset, init_data, tmp_path, global_schema
):
    tester = ModelTester(model, tmp_dir=tmp_path, global_schema=global_schema)
    tester.add_init_data(target_dataset, init_data)
    tester.add_init_data(tape_dataset_name, tape_dataset)
    return tester


def test_tape_player_sends_mask(model_tester):
    mask = model_tester.initialize()
    assert data_mask_compare(mask) == {
        "pub": {
            "dataset": {
                "entity_group": {"attribute"},
            }
        },
        "sub": {},
    }


def test_tape_player_sends_updates(model_tester, update_1, update_2):
    model_tester.initialize()
    assert model_tester.update(0, None) == (None, 1)
    assert model_tester.update(1, None) == ({"dataset": update_1}, 2)
    assert model_tester.update(2, None) == ({"dataset": update_2}, None)
    assert model_tester.update(3, None) == (None, None)


def test_multiple_tapefiles(model_tester, more_tape_data, model):
    model_tester.add_init_data("another_tapefile", more_tape_data)
    model.config = {"tabular": ["tapefile", "another_tapefile"]}
    model_tester.initialize()
    model_tester.update(0, None)
    assert model_tester.update(1, None) == (
        {
            "dataset": {
                "entity_group": {
                    "id": [0],
                    "attribute": [10],
                    "another_attribute": [11],
                }
            }
        },
        2,
    )
