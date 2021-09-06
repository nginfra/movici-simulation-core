import typing as t
from unittest.mock import Mock, call

import pytest
from model_engine import TimeStamp, Config
from model_engine.model_driver.data_handlers import DType

from movici_simulation_core.legacy_base_model.base import (
    LegacyTrackedBaseModel,
    LegacyTrackedBaseModelAdapter,
)
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import (
    field,
    PropertySpec,
    DataType,
    INIT,
    SUB,
    PUB,
)
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.testing.helpers import dataset_data_to_numpy, dataset_dicts_equal


@pytest.fixture
def config():
    class MyConfig(Config):
        PROCESS_NAME = "my_model"

    return MyConfig()


@pytest.fixture
def entity_group():
    init_spec = PropertySpec("init_prop", data_type=DataType(int, (), False))
    sub_spec = PropertySpec("sub_prop", data_type=DataType(int, (), False))
    pub_spec = PropertySpec("pub_prop", data_type=DataType(int, (), False))

    class MyEntity(EntityGroup, name="my_entities"):
        init_prop = field(init_spec, flags=INIT)
        sub_prop = field(sub_spec, flags=SUB)
        pub_prop = field(pub_spec, flags=PUB)

    return MyEntity


@pytest.fixture
def model(entity_group):
    class Model(LegacyTrackedBaseModel):
        def __init__(self):
            self.calls = []
            self.entity = None

        def setup(self, state: TrackedState, **_):
            self.entity = state.register_entity_group("dataset", entity_group)

        initialize = Mock()
        update = Mock()
        new_time = Mock()
        shutdown = Mock()

    return Model()


@pytest.fixture
def adapter(model, config):
    return LegacyTrackedBaseModelAdapter(model, name="my_model", config=config)


@pytest.fixture
def data_fetcher():
    class DataFetcher:
        def get(self, key=None):
            return DType.MSGPACK, dataset_data_to_numpy(
                {
                    "dataset": {
                        "my_entities": {
                            "id": [1, 2],
                            "init_prop": [3, 4],
                        },
                    }
                }
            )

    return DataFetcher()


@pytest.fixture
def update():
    return dataset_data_to_numpy(
        {
            "dataset": {
                "my_entities": {
                    "id": [1, 2],
                    "sub_prop": [5, 6],
                },
            }
        }
    )


def test_base_model(model, adapter, update, data_fetcher):
    assert not adapter.model_initialized
    assert model.initialize.call_count == 0
    adapter.initialize(data_fetcher)
    assert adapter.model_initialized
    assert model.initialize.call_args == call(adapter.state)

    assert not adapter.model_ready_for_update
    adapter.update(TimeStamp(0), {})
    assert not adapter.model_ready_for_update
    assert model.update.call_count == 0

    adapter.update(TimeStamp(0), update)
    assert adapter.model_ready_for_update
    assert model.update.call_count == 1


def test_get_data_filter(adapter, data_fetcher):
    adapter.initialize(data_fetcher)
    assert adapter.get_data_filter() == {
        "sub": {"dataset": {"my_entities": {"init_prop": "*", "sub_prop": "*", "id": "*"}}},
        "pub": {"dataset": {"my_entities": {"pub_prop": "*"}}},
    }


def test_new_time(adapter, model):
    assert model.new_time.call_count == 0
    adapter.new_time(TimeStamp(0))
    assert model.new_time.call_count == 1


def test_new_time_raises_when_not_initialized(adapter):
    with pytest.raises(RuntimeError):
        adapter.new_time(TimeStamp(1))


def test_shutdown_raises_when_not_initialized(adapter):
    with pytest.raises(RuntimeError):
        adapter.shutdown()


def test_new_time_accepted_when_ready_for_updates(adapter, data_fetcher, update, model):
    adapter.new_time(TimeStamp(0))
    adapter.initialize(data_fetcher)
    adapter.update(time_stamp=TimeStamp(0), update_dict=update)
    adapter.new_time(TimeStamp(1))
    assert model.new_time.call_args == call(adapter.state, TimeStamp(1))


def test_shutdown_succeeds_when_ready_for_updates(adapter, data_fetcher, update, model):
    adapter.new_time(TimeStamp(0))
    adapter.initialize(data_fetcher)
    adapter.update(time_stamp=TimeStamp(0), update_dict=update)
    adapter.shutdown()
    assert model.shutdown.call_count == 1


def test_full_run(model, adapter, update, data_fetcher, entity_group, config):
    class Model(LegacyTrackedBaseModel):
        def __init__(self):
            self.entity_group = None

        def setup(self, state: TrackedState, **_):
            self.entity_group = state.register_entity_group("dataset", entity_group)

        def initialize(self, state: TrackedState):
            self.entity_group.pub_prop[:] = -1

        def update(self, state: TrackedState, time_stamp: TimeStamp) -> t.Optional[TimeStamp]:
            self.entity_group.pub_prop[:] = time_stamp.time
            return time_stamp + 1

        new_time = Mock()
        shutdown = Mock()

    model = Model()
    adapter = LegacyTrackedBaseModelAdapter(model, "mymodel", config)
    adapter.initialize(data_fetcher)
    assert dataset_dicts_equal(
        adapter.update(TimeStamp(0), {}).data,
        dataset_data_to_numpy({"dataset": {"my_entities": {"id": [1, 2], "pub_prop": [-1, -1]}}}),
    )
    assert dataset_dicts_equal(
        adapter.update(TimeStamp(0), {}).data,
        dataset_data_to_numpy({}),
    )
    assert dataset_dicts_equal(
        adapter.update(TimeStamp(0), update).data,
        dataset_data_to_numpy({"dataset": {"my_entities": {"id": [1, 2], "pub_prop": [0, 0]}}}),
    )
    assert dataset_dicts_equal(
        adapter.update(TimeStamp(1), update).data,
        dataset_data_to_numpy({"dataset": {"my_entities": {"id": [1, 2], "pub_prop": [1, 1]}}}),
    )


def test_handles_not_ready(adapter, model, data_fetcher):
    model.initialize.side_effect = NotReady()
    adapter.initialize(data_fetcher)

    assert model.initialize.call_count == 1
    assert not adapter.model_initialized
