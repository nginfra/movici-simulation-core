import json
import typing as t
from unittest.mock import Mock

import pytest

from movici_simulation_core.data_tracker.data_format import EntityInitDataFormat
from movici_simulation_core.models.data_collector.data_collector import (
    UpdateInfo,
    DataCollector,
    LocalStorageStrategy,
)
from movici_simulation_core.testing.helpers import list_dir
from movici_simulation_core.testing.model_tester import ModelTester
from movici_simulation_core.types import UpdateData
from movici_simulation_core.utils.settings import Settings


@pytest.fixture
def storage_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("storage")


@pytest.fixture
def model_config(tmp_path_factory, storage_dir):
    return {
        "gather_filter": None,
        "storage_dir": str(storage_dir),
    }


@pytest.fixture
def settings(storage_dir):
    return Settings(storage_dir=storage_dir)


@pytest.fixture
def model(model_config):
    return DataCollector(model_config)


def test_picks_strategy(model):
    settings = Settings(storage="disk")
    assert isinstance(model.get_storage_strategy(settings), LocalStorageStrategy)


def test_local_storage_strategy_stores_update(tmp_path):
    strat = LocalStorageStrategy(tmp_path)
    upd = {"dataset": {"entity_group": {"id": [1, 2, 3]}}}
    info = UpdateInfo("dataset", 1, 2, EntityInitDataFormat().load_json(upd)["dataset"])
    strat.store(info)
    assert json.loads((tmp_path / "t1_2_dataset.json").read_text()) == upd


MISSING = object()


@pytest.mark.parametrize(
    "sub_mask, expected",
    [(None, None), ("*", None), (MISSING, None), ({"dataset": None}, {"dataset": None})],
)
def test_get_datamask(model, sub_mask, expected, settings):
    model.config = {"gather_filter": sub_mask} if sub_mask is not MISSING else {}
    assert model.initialize(settings) == {"pub": {}, "sub": expected}


def run_updates(model, updates: t.Sequence[t.Tuple[int, UpdateData]]):
    tester = ModelTester(model)
    tester.initialize()
    for timestamp, data in updates:
        tester.update(timestamp, data)
    tester.close()


def test_stores_one_update(model, storage_dir):
    upd = {"some_dataset": {"some_entities": {"id": [1], "attr": [10]}}}
    run_updates(model, [(0, upd)])

    assert json.loads((storage_dir / "t0_0_some_dataset.json").read_text()) == upd


def test_stores_multiple_updates(model, storage_dir):
    run_updates(
        model,
        [
            (0, {"some_dataset": {"some_entities": {"id": [1], "attr": [10]}}}),
            (0, {"other_dataset": {"some_entities": {"id": [1], "attr": [10]}}}),
        ],
    )
    assert {"t0_0_some_dataset.json", "t0_1_other_dataset.json"}.issubset(
        set(list_dir(storage_dir))
    )


def test_submits_job_per_dataset(model):
    model.submit = Mock()
    run_updates(
        model,
        [
            (
                0,
                {
                    "some_dataset": {"some_entities": {"id": [1], "attr": [10]}},
                    "other_dataset": {"some_entities": {"id": [1], "attr": [10]}},
                },
            )
        ],
    )
    assert model.submit.call_count == 2


def test_only_submits_on_changed_data(model):
    model.submit = Mock()
    run_updates(
        model,
        [
            (0, {"dataset": {"some_entities": {"id": [1], "attr": [10]}}}),
            (0, {"dataset": {"some_entities": {"id": [1], "attr": [10]}}}),
        ],
    )
    assert model.submit.call_count == 1


def test_can_aggregate_updates_on_newtime(model, settings, storage_dir):
    model.config["aggregate_updates"] = True
    tester = ModelTester(model, settings)
    tester.initialize()
    tester.new_time(0)
    tester.update(0, {"dataset": {"some_entities": {"id": [1, 2], "attr": [10, 20]}}})
    tester.update(0, {"dataset": {"some_entities": {"id": [2], "attr": [21]}}})
    assert "t0_0_dataset.json" not in list_dir(storage_dir)
    tester.new_time(1)
    tester.close()
    assert "t0_0_dataset.json" in list_dir(storage_dir)
    assert "t0_1_dataset.json" not in list_dir(storage_dir)
    assert json.loads((storage_dir / "t0_0_dataset.json").read_text()) == {
        "dataset": {"some_entities": {"id": [1, 2], "attr": [10, 21]}}
    }
