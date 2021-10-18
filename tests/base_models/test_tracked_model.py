import json
import typing as t
from unittest.mock import Mock, call

import numpy as np
import pytest

from movici_simulation_core.base_models.tracked_model import (
    TrackedModelAdapter,
    TrackedModel,
)
from movici_simulation_core.data_tracker.data_format import dump_update, load_update
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
from movici_simulation_core.model_connector.init_data import FileType
from movici_simulation_core.networking.messages import (
    UpdateMessage,
    NewTimeMessage,
    QuitMessage,
    UpdateSeriesMessage,
)
from movici_simulation_core.testing.helpers import dataset_data_to_numpy, dataset_dicts_equal
from movici_simulation_core.utils.moment import Moment


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
    class Model(TrackedModel):
        def __init__(self, config=None):
            super().__init__(config)
            self.entity = None

        def setup(self, state: TrackedState, **_):
            self.entity = state.register_entity_group("dataset", entity_group)

        initialize = Mock()
        update = Mock()
        new_time = Mock()
        shutdown = Mock()
        install = Mock()

    return Model()


@pytest.fixture
def get_adapter(settings):
    def _get_adapter(model, override_settings=None):
        return TrackedModelAdapter(model, settings=override_settings or settings, logger=Mock())

    return _get_adapter


@pytest.fixture
def adapter(model, get_adapter) -> TrackedModelAdapter:
    return get_adapter(model)


@pytest.fixture
def create_update(entity_group):
    def _create(payload):
        return dump_update(
            dataset_data_to_numpy({"dataset": {entity_group.__entity_name__: payload}})
        )

    return _create


@pytest.fixture
def update(create_update):
    return create_update(
        {
            "id": [1, 2],
            "sub_prop": [5, 6],
        }
    )


@pytest.fixture
def init_data_handler(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(
        json.dumps(
            {
                "dataset": {
                    "my_entities": {
                        "id": [1, 2],
                        "init_prop": [3, 4],
                    },
                }
            }
        )
    )

    class FakeInitDataHandler:
        def get(self, key=None):
            return FileType.JSON, path

    return FakeInitDataHandler()


def test_base_model(model, adapter, update, init_data_handler):
    assert not adapter.model_initialized
    assert model.initialize.call_count == 0
    adapter.initialize(init_data_handler)
    assert adapter.model_initialized
    assert model.initialize.call_args == call(adapter.state)

    assert not adapter.model_ready_for_update
    adapter.update(UpdateMessage(0), None)
    assert not adapter.model_ready_for_update
    assert model.update.call_count == 0

    adapter.update(UpdateMessage(0), update)
    assert adapter.model_ready_for_update
    assert model.update.call_count == 1


def test_get_data_filter(adapter, init_data_handler):
    adapter.initialize(init_data_handler)
    assert adapter.get_data_filter() == {
        "sub": {"dataset": {"my_entities": ["init_prop", "sub_prop"]}},
        "pub": {"dataset": {"my_entities": ["pub_prop"]}},
    }


def test_new_time(adapter, model):
    assert model.new_time.call_count == 0
    adapter.new_time(NewTimeMessage(0))
    assert model.new_time.call_count == 1


def test_new_time_raises_when_not_initialized(adapter):
    with pytest.raises(RuntimeError):
        adapter.new_time(NewTimeMessage(1))


def test_new_time_raises_when_not_ready_for_updates(adapter):
    adapter.model_initialized = True
    with pytest.raises(RuntimeError):
        adapter.new_time(NewTimeMessage(1))


def test_shutdown_raises_when_not_initialized(adapter):
    with pytest.raises(RuntimeError):
        adapter.close(QuitMessage())


def test_shutdown_raises_when_not_ready_for_updates(adapter):
    adapter.model_initialized = True
    with pytest.raises(RuntimeError):
        adapter.close(QuitMessage())


def test_new_time_accepted_when_ready_for_updates(adapter, init_data_handler, update, model):
    adapter.new_time(NewTimeMessage(0))
    adapter.initialize(init_data_handler)
    adapter.update(UpdateMessage(0), update)
    adapter.new_time(NewTimeMessage(1))
    assert model.new_time.call_args == call(adapter.state, Moment(1))


def test_shutdown_succeeds_when_ready_for_updates(adapter, init_data_handler, update, model):
    adapter.new_time(NewTimeMessage(0))
    adapter.initialize(init_data_handler)
    adapter.update(UpdateMessage(0), update)
    adapter.close(QuitMessage())
    assert model.shutdown.call_count == 1


def test_full_run(model, get_adapter, update, init_data_handler, entity_group):
    class Model(TrackedModel):
        def __init__(self):
            self.entity_group = None

        def setup(self, state: TrackedState, **_):
            self.entity_group = state.register_entity_group("dataset", entity_group)

        def initialize(self, state: TrackedState):
            self.entity_group.pub_prop[:] = -1

        def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
            self.entity_group.pub_prop[:] = moment.timestamp
            return Moment(moment.timestamp + 1)

        new_time = Mock()
        shutdown = Mock()
        install = Mock()

    model = Model()
    adapter = get_adapter(model)
    adapter.initialize(init_data_handler)

    def compare_update_result(timestamp, raw_update, expected):
        raw_result = adapter.update(UpdateMessage(timestamp), raw_update)[0]
        assert dataset_dicts_equal(
            load_update(raw_result) if raw_result is not None else {},
            dataset_data_to_numpy(expected),
        )

    compare_update_result(
        0, None, {"dataset": {"my_entities": {"id": [1, 2], "pub_prop": [-1, -1]}}}
    )
    compare_update_result(0, None, {})
    compare_update_result(
        0, update, {"dataset": {"my_entities": {"id": [1, 2], "pub_prop": [0, 0]}}}
    )
    compare_update_result(
        1, update, {"dataset": {"my_entities": {"id": [1, 2], "pub_prop": [1, 1]}}}
    )


def test_handles_not_ready(adapter, model, init_data_handler):
    model.initialize.side_effect = NotReady()
    adapter.initialize(init_data_handler)

    assert model.initialize.call_count == 1
    assert not adapter.model_initialized


class TestUpdate:
    @pytest.fixture
    def filtered_update(self):
        return dump_update({})

    def test_skips_calculation_on_empty_cascading_update(self, adapter, model, filtered_update):
        adapter.update(UpdateMessage(1, "bla", "bla"), filtered_update)
        assert not model.update.call_count

    def test_remembers_next_time_when_skipping_cascading_update(
        self, adapter, model, filtered_update
    ):
        model.update.return_value = 12
        adapter.update(UpdateMessage(1), None)
        result = adapter.update(UpdateMessage(1), filtered_update)
        assert result == (None, 12)


class TestUpdateSeries:
    @pytest.fixture
    def message(self):
        return UpdateSeriesMessage(
            updates=[UpdateMessage(0, "key_a", "address"), UpdateMessage(0, "key_b", "address")]
        )

    @pytest.fixture
    def data(self, create_update):
        return [
            create_update({"id": [1], "sub_prop": [1]}),
            create_update({"id": [2], "sub_prop": [2]}),
        ]

    @pytest.fixture
    def adapter(self, adapter, init_data_handler):
        adapter.initialize(init_data_handler)
        return adapter

    def test_calls_model_once(self, adapter, model, message, data):
        adapter.update_series(message, data)
        assert model.update.call_count == 1

    def test_processes_all_data(self, adapter, model, message, data):
        adapter.update_series(message, data)
        np.testing.assert_array_equal(
            adapter.state.properties["dataset"]["my_entities"][(None, "sub_prop")].array, [1, 2]
        )
